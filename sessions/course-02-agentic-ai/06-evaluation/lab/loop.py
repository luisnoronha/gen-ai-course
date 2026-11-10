"""The self-improvement loop.

    run the agent on the training cases
      -> the critic reviews every run            (starter/improver.py: describe_run, build_critic)
      -> the proposer changes ONE thing          (starter/improver.py: build_proposer, proposer_message, recall)
      -> run the new version on the same cases
      -> keep it or not                          (by the case checks: starter/decision.py; or by the critic's score)
      -> write a lesson to memory                (starter/improver.py: lesson)
    ...repeat, then test the best version on reserved cases it never saw.

This file only runs the loop. The parts that think are the students' (pieces.py falls back to defaults).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic_ai.usage import UsageLimits

import agents
import critic
import pieces
import suite
from models import Proposal, Review

TRAINING = ("s01-gateway-latency", "s01-alert-cleared-errors", "s02-firewall-change", "s02-noisy-gateway", "s02-lost-response")
RESERVED = ("s01-stale-alert", "s01-market-data-delay", "s01-metrics-unavailable", "s01-flaky-metrics", "s02-hidden-config-change")

@dataclass
class Evaluation:
    version: agents.Version
    results: list[suite.RunResult]
    reviews: list[Review] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return suite.pass_rate(self.results)

    @property
    def score(self) -> float:
        return sum(r.score for r in self.reviews) / len(self.reviews) if self.reviews else 0.0

    @property
    def tokens(self) -> float:
        return sum(r.tokens for r in self.results) / max(1, len(self.results))


@dataclass
class Attempt:
    iteration: int
    change: str
    kept: bool
    reason: str
    train_before: float
    train_after: float
    score_before: float
    score_after: float
    instructions: str = ""


@dataclass
class Loop:
    start: agents.Version
    critic_prompt: str
    accept_by: Literal["checks", "critic"] = "checks"
    repetitions: int = 2
    best: Evaluation | None = None
    attempts: list[Attempt] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    reserved: tuple[Evaluation, Evaluation] | None = None
    who: dict[str, str] = field(default_factory=dict)  # each piece: "yours", "default" or "none"
    last_message: str = ""  # what the proposer read last time

    # One evaluation: run, then let the critic review every run ---------------------------------

    def evaluate(self, version: agents.Version, cases: tuple[str, ...], model: Any, progress: Callable[[str], None], reviews: bool = True) -> Evaluation:
        found = suite.cases()
        jobs = [(version, case, found[case]) for case in cases for _ in range(self.repetitions)]
        results = suite.run_many(jobs, model, on_done=lambda done, total: progress(f"{version.name}: run {done}/{total}"))
        evaluation = Evaluation(version, results)
        if reviews:
            progress(f"{version.name}: the critic reviews {len(results)} runs")
            evaluation.reviews, self.who["critic agent"] = critic.review_all(model, self.critic_prompt, [r.description for r in results])
            self.who["what the critic sees"] = results[0].description_origin if results else "default"
        return evaluation

    def begin(self, model: Any, progress: Callable[[str], None] = print) -> None:
        self.best = self.evaluate(self.start, TRAINING, model, progress)

    # One iteration ------------------------------------------------------------------------------

    def memory_text(self) -> str:
        text, self.who["memory: recall"] = pieces.recall(self.lessons)
        return text

    def propose(self, model: Any) -> Proposal:
        reviews = [(result.case, review) for result, review in zip(self.best.results, self.best.reviews)]
        message, self.who["what the proposer reads"] = pieces.proposer_message(
            self.best.version.instructions, self.best.version.verify_recovery, reviews, self.memory_text())
        self.last_message = message
        agent, self.who["proposer agent"] = pieces.proposer_agent(model)
        return agent.run_sync(message, usage_limits=UsageLimits(request_limit=3)).output

    def judge_change(self, before: Evaluation, after: Evaluation) -> tuple[bool, str]:
        if self.accept_by == "critic":
            kept = after.score > before.score
            return kept, f"critic score {before.score:.2f} -> {after.score:.2f}"
        decision = suite.load_starter("decision")
        comparisons = []
        for case in TRAINING:
            base = [r for r in before.results if r.case == case]
            cand = [r for r in after.results if r.case == case]
            comparisons.append(decision.CaseComparison(case, sum(r.passed for r in base), len(base), sum(r.passed for r in cand), len(cand)))
        try:
            verdict = decision.decide(comparisons, before.tokens, after.tokens)
        except NotImplementedError:
            kept = after.pass_rate > before.pass_rate
            return kept, f"pass rate {before.pass_rate:.0%} -> {after.pass_rate:.0%} (decision.py not written: kept only if higher)"
        return verdict.adopt is True, "; ".join(verdict.reasons) or str(verdict.adopt)

    def step(self, model: Any, progress: Callable[[str], None] = print) -> Attempt:
        if self.best is None:
            self.begin(model, progress)
        number = len(self.attempts) + 1
        progress(f"Iteration {number}: the proposer reads the reviews and its memory")
        proposal = self.propose(model)
        # Keep the start's builder: for C (the students' agent) the loop changes only its instructions.
        candidate = agents.Version(f"v{number}", proposal.instructions, proposal.verify_recovery, proposal.change, self.best.version.builder)
        after = self.evaluate(candidate, TRAINING, model, progress)
        kept, reason = self.judge_change(self.best, after)
        attempt = Attempt(number, proposal.change, kept, reason, self.best.pass_rate, after.pass_rate, self.best.score, after.score, proposal.instructions)
        self.attempts.append(attempt)
        line, self.who["memory: lesson"] = pieces.lesson(attempt)
        if line:
            self.lessons.append(line)
        if kept:
            self.best = after
        return attempt

    # The final test -------------------------------------------------------------------------------

    def test_reserved(self, model: Any, progress: Callable[[str], None] = print) -> tuple[Evaluation, Evaluation]:
        first = self.evaluate(self.start, RESERVED, model, progress, reviews=False)
        best = self.evaluate(self.best.version, RESERVED, model, progress, reviews=False)
        self.reserved = (first, best)
        return self.reserved

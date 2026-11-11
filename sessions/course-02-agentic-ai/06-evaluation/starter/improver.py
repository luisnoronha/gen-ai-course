"""Exercise — Build the agents that improve the agent.

In tab 2 a loop tries to improve the incident agent by itself:
run the cases -> a CRITIC reviews each run -> a PROPOSER changes one thing -> keep it or not -> MEMORY.
The lab only runs the cases and shows the results. You write every part that thinks:

1. describe_run(run): what the critic sees about one run of the incident agent.
2. build_critic(model, instructions): the critic agent. It reads one description and returns a Review.
   instructions is the lab's default critic prompt (lab/critic_prompt.md): weak on purpose. Write a better one.
3. build_proposer(model): the proposer agent. It returns a Proposal: one change, and the complete new
   instructions for the incident agent.
4. proposer_message(...): what the proposer reads before each change.
5. lesson(attempt) and recall(lessons): the proposer's memory, between attempts.

Until you write a piece, the lab uses a simple default for it. Tab 2 shows, for each piece, whether the last
run used yours or the default. Click Reset in tab 2 after editing this file.

You may use an AI assistant to write this file. Then read it: you must be able to explain what each agent
sees, what it may change, and why a change it proposes cannot fool the decision.

Hints:
- The critic only improves what it can see (slide "O crítico só melhora o que consegue ver").
- What stops the proposer from tuning the instructions to the five training cases? From pleasing the critic?
- A failed attempt is as useful to remember as a kept one.
- An Attempt has: iteration, change, kept, reason, train_before, train_after, score_before, score_after.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai import Agent

from meridian.agent_runtime import IncidentRun

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
from models import Proposal, Review  # noqa: E402


# 1 · What the critic sees ------------------------------------------------------------------


def describe_run(run: IncidentRun) -> str:
    # run.trace: tool calls (call.tool, call.args, call.result, call.error); run.evaluation.checks; run.report
    raise NotImplementedError


# 2 · The critic ------------------------------------------------------------------------------


def build_critic(model, instructions: str) -> Agent[None, Review]:
    raise NotImplementedError


# 3 · The proposer ----------------------------------------------------------------------------


def build_proposer(model) -> Agent[None, Proposal]:
    raise NotImplementedError


# 4 · What the proposer reads -----------------------------------------------------------------


def proposer_message(instructions: str, verify_recovery: bool, reviews: list[tuple[str, Review]], memory: str) -> str:
    # reviews: (case name, the critic's Review) for every run of the current best version
    raise NotImplementedError


# 5 · Memory ----------------------------------------------------------------------------------


def lesson(attempt) -> str | None:
    raise NotImplementedError


def recall(lessons: list[str]) -> str:
    raise NotImplementedError

"""The incident team: the agents, their tools, and the room they work in.

Agents (the lab gives you these four):
- network:     reads links, recent changes, gateway logs. Changes nothing.
- database:    reads reference-db, its logs and the tickets (planned work). Changes nothing.
- remediation: acts: roll back a change, move the gateway to another site. Every action needs the on-call's approval.
- reviewer:    reads the real state after the work and says whether the incident is over.

You write how they work together:
- starter/pipeline.py:  a fixed sequence, in code.
- starter/orchestrator.py: an agent that decides whom to ask, and when.

Team.ask(name, message) sends a message to one agent and returns its answer as text. Everything an agent does
appears live on the board: who is working, what it reads, what it asks the on-call to approve.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from world import HERE, World

STARTER = HERE.parent / "starter"
SOLUTIONS = HERE.parents[3] / "private" / "course-02-agentic-ai" / "reference" / "session-07"
APPROVAL_TIMEOUT_S = 300


def use_solutions() -> bool:
    """Trainer only: LAB_SOLUTIONS=1 runs the solutions instead of starter/, without touching starter/."""
    return os.environ.get("LAB_SOLUTIONS") == "1" and SOLUTIONS.is_dir()


def load_starter(name: str):
    folder = SOLUTIONS if use_solutions() else STARTER
    spec = importlib.util.spec_from_file_location(f"s07_{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"s07_{name}"] = module
    spec.loader.exec_module(module)
    return module


# What the agents return -------------------------------------------------------------------------


class Finding(BaseModel):
    cause: str
    evidence: list[str]
    constraints: list[str]  # facts that limit what the others may do


class RemediationReport(BaseModel):
    status: Literal["resolved", "not_resolved"]
    actions: list[str]
    summary: str


class Review(BaseModel):
    recovered: bool
    reason: str


class Outcome(BaseModel):
    """What the orchestrator reports at the end."""

    status: Literal["resolved", "unresolved"]
    root_cause: str
    summary: str


# The room ---------------------------------------------------------------------------------------


@dataclass
class Team:
    model: Any
    incident: str
    approvals: Literal["auto", "human"] = "auto"
    reviewer: bool = False
    world: World = field(init=False)
    cards: dict[str, dict[str, str]] = field(default_factory=dict)  # agent -> {status, activity}
    feed: list[dict[str, str]] = field(default_factory=list)  # messages, actions and approvals, in order
    pending: dict[str, Any] | None = None  # an approval waiting for the on-call
    reported: str = "no report"
    outcome: Outcome | None = None
    error: str | None = None
    running: bool = False
    seconds: float = 0.0
    requests: int = 0
    tokens: int = 0
    sender: str = "pipeline"  # who sends the messages of Team.ask

    def __post_init__(self) -> None:
        self.world = World(self.incident)
        self._lock = threading.Lock()

    @property
    def brief(self) -> str:
        info = self.world.sim.incident_brief()
        return f"Incident {info['incident_id']} ({info['time']}): {info['summary']} Related alert: {info['alert_id']}."

    # The board -------------------------------------------------------------------------------

    def set_card(self, agent: str, status: str, activity: str = "") -> None:
        self.cards[agent] = {"status": status, "activity": activity}

    def post(self, sender: str, to: str, text: str, kind: str = "message") -> None:
        self.feed.append({"time": self.world.sim.clock.label(self.world.sim.state.tick), "from": sender, "to": to, "text": text, "kind": kind})

    # Talking to an agent ---------------------------------------------------------------------

    async def ask(self, name: str, message: str) -> str:
        """Send `message` to one agent (network, database, remediation, reviewer) and return its answer as text."""
        if name not in AGENTS:
            raise ValueError(f"Unknown agent {name!r}. Agents: {', '.join(AGENTS)}")
        self.post(self.sender, name, message)
        self.set_card(name, "working", "Reading the task…")
        try:
            result = await build(name, self).run(message, deps=Seat(self, name), usage_limits=UsageLimits(request_limit=30))
        except Exception as error:
            self.set_card(name, "error", str(error)[:200])
            raise
        with self._lock:
            usage = result.usage
            self.requests += usage.requests
            self.tokens += (usage.input_tokens or 0) + (usage.output_tokens or 0)
        answer = result.output
        if isinstance(answer, RemediationReport):
            self.reported = "resolved" if answer.status == "resolved" else "unresolved"
        text = render(answer)
        self.set_card(name, "done", text)
        self.post(name, self.sender, text, "answer")
        return text

    # Approvals: the on-call engineer ---------------------------------------------------------

    def ask_approval(self, agent: str, action: str, target: str, reason: str) -> tuple[str | None, str]:
        """Blocks the agent until the on-call answers. Returns (approval_ref or None, comment)."""
        self.post(agent, "on-call", f"Approve {action} {target}? {reason}", "approval")
        if self.approvals == "auto":
            self.post("on-call", agent, "Approved (auto).", "approved")
            return self.world.approve(action, target, reason, "auto"), ""
        decided = threading.Event()
        self.pending = {"agent": agent, "action": action, "target": target, "reason": reason, "event": decided, "approved": False, "comment": ""}
        self.set_card(agent, "waiting", f"Waiting for your approval: {action} {target}")
        self.set_card("on-call", "waiting", f"{agent} asks: {action} {target}")
        answered = decided.wait(APPROVAL_TIMEOUT_S)
        pending, self.pending = self.pending, None
        approved = answered and pending["approved"]
        comment = pending["comment"] if answered else "No answer from the on-call."
        self.set_card("on-call", "done", ("Approved" if approved else "Rejected") + f": {action} {target}" + (f" — {comment}" if comment else ""))
        self.set_card(agent, "working", "Approved, acting…" if approved else "Rejected, changing the plan…")
        self.post("on-call", agent, ("Approved." if approved else "Rejected.") + (f" {comment}" if comment else ""), "approved" if approved else "rejected")
        return (self.world.approve(action, target, reason, "on-call") if approved else None), comment

    def answer(self, approved: bool, comment: str = "") -> None:
        """Called by the app when the on-call clicks."""
        if self.pending:
            self.pending.update(approved=approved, comment=comment.strip())
            self.pending["event"].set()

    # Running a pattern -------------------------------------------------------------------------

    def start(self, pattern) -> threading.Thread:
        """Run `pattern(team)` (an async function) in the background, so the board can update live."""
        self.running = True
        thread = threading.Thread(target=self._run, args=(pattern,), daemon=True)
        thread.start()
        return thread

    def _run(self, pattern) -> None:
        began = time.monotonic()
        try:
            asyncio.run(self._main(pattern))
        except NotImplementedError as missing:
            self.error = f"Not written yet: {missing}" if str(missing) else "This starter file is not written yet."
        except Exception as error:  # Keep the board when a run fails.
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self, pattern) -> None:
        await pattern(self)
        if self.reviewer:
            await self.review()

    async def review(self) -> None:
        """The reviewer checks the real state. If it is not over, remediation gets one more try."""
        for attempt in range(2):
            self.sender = "team"
            verdict = await self._review()
            if verdict.recovered:
                self.reported = "resolved"
                return
            self.reported = "unresolved"
            if attempt == 0:
                self.sender = "reviewer"
                await self.ask("remediation", f"The reviewer checked the real state: the incident is NOT over. {verdict.reason} Fix it.")

    async def _review(self) -> Review:
        self.post("team", "reviewer", "Is the incident over? Check the real state.")
        self.set_card("reviewer", "working", "Checking the real state…")
        result = await build("reviewer", self).run("Is the incident over? Check the real state.", deps=Seat(self, "reviewer"))
        verdict = result.output
        self.set_card("reviewer", "done", ("Recovered. " if verdict.recovered else "NOT recovered. ") + verdict.reason)
        self.post("reviewer", "team", ("Recovered. " if verdict.recovered else "Not recovered. ") + verdict.reason, "answer")
        return verdict


def render(answer: Any) -> str:
    if isinstance(answer, Finding):
        text = f"Cause: {answer.cause}\nEvidence: {'; '.join(answer.evidence) or '-'}"
        return text + (f"\nConstraints: {'; '.join(answer.constraints)}" if answer.constraints else "")
    if isinstance(answer, RemediationReport):
        return f"{answer.status}. Actions: {'; '.join(answer.actions) or 'none'}. {answer.summary}"
    if isinstance(answer, BaseModel):
        return json.dumps(answer.model_dump())
    return str(answer)


@dataclass
class Seat:
    """Who is calling a tool: the team, and the agent's name."""

    team: Team
    name: str


# Tools ------------------------------------------------------------------------------------------


def _show(ctx: RunContext[Seat], text: str) -> None:
    ctx.deps.team.set_card(ctx.deps.name, "working", text)


def read_metrics(ctx: RunContext[Seat], component: str) -> dict[str, Any]:
    """Recent metrics of a component (latency_ms, error_rate)."""
    _show(ctx, f"Reading metrics of {component}")
    return ctx.deps.team.world.call("read_metrics", component, 3)


def read_logs(ctx: RunContext[Seat], component: str, contains: str | None = None) -> dict[str, Any]:
    """Recent log lines of a component; contains filters, e.g. "WARN"."""
    _show(ctx, f"Reading logs of {component}")
    return ctx.deps.team.world.call("read_logs", component=component, contains=contains, limit=15)


def check_link(ctx: RunContext[Seat], source: str, target: str) -> dict[str, Any]:
    """State of the link between two components: up, degraded or down."""
    _show(ctx, f"Checking link {source} → {target}")
    return ctx.deps.team.world.call("check_link", source, target)


def recent_changes(ctx: RunContext[Seat], component: str | None = None) -> dict[str, Any]:
    """Recent deploys and configuration changes."""
    _show(ctx, "Looking for recent changes")
    return ctx.deps.team.world.call("recent_changes", component, 5)


def search_tickets(ctx: RunContext[Seat], text: str | None = None, component: str | None = None) -> dict[str, Any]:
    """Search tickets: member incidents and planned work (maintenance windows)."""
    _show(ctx, f"Searching tickets {text or component or ''}".strip())
    return ctx.deps.team.world.call("search_tickets", text=text, component=component)


def read_ticket(ctx: RunContext[Seat], key: str) -> dict[str, Any]:
    """Read one ticket, e.g. MRX-4790."""
    _show(ctx, f"Reading ticket {key}")
    return ctx.deps.team.world.call("read_ticket", key)


def rollback_change(ctx: RunContext[Seat], change_id: str, reason: str) -> dict[str, Any]:
    """Undo a configuration change, e.g. CHG-4750. Asks the on-call for approval first."""
    team = ctx.deps.team
    ref, comment = team.ask_approval(ctx.deps.name, "rollback_change", change_id, reason)
    if ref is None:
        return {"status": "rejected by the on-call", "comment": comment}
    result = team.world.call("rollback_change", change_id, idempotency_key=f"s07:{change_id}", confirmation_ref=ref)
    team.post(ctx.deps.name, "world", f"rollback_change {change_id}: {result.get('outcome', result)}", "action")
    return result


def failover_gateway(ctx: RunContext[Seat], site: Literal["A", "B", "C"], reason: str) -> dict[str, Any]:
    """Move order-gateway to another site. Asks the on-call for approval first."""
    team = ctx.deps.team
    ref, comment = team.ask_approval(ctx.deps.name, "failover_gateway", f"site-{site}", reason)
    if ref is None:
        return {"status": "rejected by the on-call", "comment": comment}
    result = team.world.failover_gateway(site, ref, ctx.deps.name)
    team.post(ctx.deps.name, "world", f"failover_gateway site-{site}: {result.get('outcome', result)}", "action")
    return result


def gateway_state(ctx: RunContext[Seat]) -> dict[str, Any]:
    """Where the gateway runs now, and its latest latency and error rate."""
    _show(ctx, "Reading the gateway's state")
    return ctx.deps.team.world.gateway_now()


# The agents -------------------------------------------------------------------------------------

SITES = "Sites: A (primary, where order-gateway runs), B (standby), C (disaster recovery, fully independent)."

NETWORK = ("You are the network specialist of the Meridian Exchange incident team. Investigate the question you get: "
           "the link from order-gateway to reference-db, recent changes, the gateway's logs. Do not change anything. "
           "Report the cause, the evidence and any constraint the others must respect. " + SITES)
DATABASE = ("You are the database specialist of the Meridian Exchange incident team. Investigate the question you get: "
            "reference-db's health and logs, and tickets about planned work on it. Do not change anything. "
            "Report the cause, the evidence and any constraint the others must respect (for example a maintenance window). " + SITES)
REMEDIATION = ("You are the remediation specialist of the Meridian Exchange incident team. Carry out the task you get with your tools. "
               + SITES + " If a change caused the problem, roll it back. If site A's network itself is failing, the standard move "
               "is to fail over order-gateway to site B; use site C only if site B cannot be used. Respect every constraint in your task. "
               "Every action asks the on-call for approval: if they reject it, read their comment and change the plan. "
               "Afterwards read the gateway's metrics and report.")
REVIEWER = ("You are the reviewer of the Meridian Exchange incident team. Do not trust what the others say: check the real state. "
            "The incident is over only if order-gateway's latency is below 20 ms and its error rate below 1%, now. "
            "If it is not over, say why, with what you saw (logs help).")

AGENTS: dict[str, tuple[str, type[BaseModel], tuple]] = {
    "network": (NETWORK, Finding, (read_metrics, read_logs, check_link, recent_changes)),
    "database": (DATABASE, Finding, (read_metrics, read_logs, search_tickets, read_ticket)),
    "remediation": (REMEDIATION, RemediationReport, (read_metrics, gateway_state, rollback_change, failover_gateway)),
    "reviewer": (REVIEWER, Review, (gateway_state, read_metrics, read_logs)),
}


def build(name: str, team: Team) -> Agent[Seat, Any]:
    instructions, output, tools = AGENTS[name]
    return Agent(team.model, deps_type=Seat, output_type=output, instructions=instructions, tools=tools)


# The patterns -----------------------------------------------------------------------------------


async def runbook(team: Team) -> None:
    """The demo's pipeline: the runbook for a latency alert. Network investigates, remediation fixes."""
    team.sender = "pipeline"
    finding = await team.ask("network", f"{team.brief} Find the cause of the latency.")
    await team.ask("remediation", f"{team.brief}\nThe network specialist found:\n{finding}\nMitigate the incident.")


async def students_pipeline(team: Team) -> None:
    team.sender = "pipeline"
    await load_starter("pipeline").run_pipeline(team)


async def students_orchestrator(team: Team) -> None:
    orchestrator = load_starter("orchestrator").build_orchestrator(team.model)
    team.sender = "orchestrator"
    team.set_card("orchestrator", "working", "Reading the incident…")
    result = await orchestrator.run(team.brief, deps=team, usage_limits=UsageLimits(request_limit=40))
    with team._lock:
        usage = result.usage
        team.requests += usage.requests
        team.tokens += (usage.input_tokens or 0) + (usage.output_tokens or 0)
    team.outcome = result.output
    if isinstance(result.output, Outcome):
        team.reported = result.output.status
    team.set_card("orchestrator", "done", render(result.output))

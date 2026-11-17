"""Exercise 3: the incident room, the crash, and the resume.

The lab runs the first half of the incident (investigation, plan, approvals, the failover) and saves a checkpoint
after each step. Then the process "crashes" (a shift change). Your starter/resume.py continues from the checkpoint.

What your resume gets: the checkpoint read back from its file (a dict, also shown on the page), and the `room`:
- await room.ask(name, message)    send a task to an agent and get its answer as text: "remediation" or "reviewer"
- room.history()                   every action the systems really ran (action, target, key, time). Survives the crash.
- room.approval_status(ref)        is an approval still valid now? (valid, reason)
- room.note(text)                  write a line on the board, so you can see what your code decided
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

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep the terminal quiet: the board shows every call
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import UsageLimits
from world import BATCH, HERE, World

STARTER = HERE.parent / "starter"
SOLUTIONS = HERE.parents[3] / "private" / "course-02-agentic-ai" / "reference" / "session-08"
RUNS = HERE / ".runs"  # checkpoints are files: they survive the crash
MAX_STEPS = 12
STEP_DELAY = 0.6  # seconds between the steps of the first half, so the board can be followed

SCENARIOS = {
    "A · Crash after the resend": "after_resend",
    "B · Crash, then a long pause": "long_pause",
}
PAUSE = {"after_resend": 5, "long_pause": 40}  # minutes nobody works


def use_solutions() -> bool:
    """Trainer only: LAB_SOLUTIONS=1 runs the solutions instead of starter/, without touching starter/."""
    return os.environ.get("LAB_SOLUTIONS") == "1" and SOLUTIONS.is_dir()


def load_starter(name: str):
    folder = SOLUTIONS if use_solutions() else STARTER
    spec = importlib.util.spec_from_file_location(f"s08_{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"s08_{name}"] = module
    spec.loader.exec_module(module)
    return module


def patient(model: Any) -> Any:
    """An OpenAI model that retries more when rate-limited. Built inside the run's event loop."""
    if not (isinstance(model, str) and model.startswith("openai:")):
        return model
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    return OpenAIChatModel(model.removeprefix("openai:"), provider=OpenAIProvider(openai_client=AsyncOpenAI(max_retries=6)))


class RemediationReport(BaseModel):
    status: Literal["done", "not_done"]
    actions: list[str]
    summary: str


class Review(BaseModel):
    recovered: bool
    clean: bool  # no action ran twice
    reason: str


# The room -----------------------------------------------------------------------------------------


@dataclass
class Room:
    model: Any
    scenario: str  # a value of SCENARIOS
    scenario_label: str = ""  # A or B, for the table of runs
    world: World = field(default_factory=World)
    cards: dict[str, dict[str, str]] = field(default_factory=dict)
    feed: list[dict[str, str]] = field(default_factory=list)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    running: bool = False
    crashed: bool = False
    seconds: float = 0.0
    requests: int = 0
    sender: str = "team"

    def __post_init__(self) -> None:
        info = self.world.sim.incident_brief()
        self.brief = f"Incident {info['incident_id']} ({info['time']}): {info['summary']}"
        self.path = RUNS / f"checkpoint-{self.scenario}.json"

    # The board ---------------------------------------------------------------------------------

    def set_card(self, agent: str, status: str, activity: str = "") -> None:
        self.cards[agent] = {"status": status, "activity": activity}

    def post(self, sender: str, to: str, text: str, kind: str = "message") -> None:
        self.feed.append({"time": self.world.now(), "from": sender, "to": to, "text": text, "kind": kind})

    def note(self, text: str) -> None:
        """For your resume: write a line on the board."""
        self.post("resume", "board", text, "note")
        self.set_card("resume", "working", text)

    # What the resume can use -------------------------------------------------------------------

    def history(self) -> list[dict[str, Any]]:
        """Every action the systems really ran. Survives the crash."""
        self.post("resume", "systems", f"history → {len(self.world.effects)} actions", "tool")
        return self.world.history()

    def approval_status(self, ref: str) -> dict[str, Any]:
        """Is this approval still valid now?"""
        status = self.world.approval_status(ref)
        self.post("resume", "systems", f"approval_status {ref} → {'valid' if status['valid'] else 'NOT valid'}: {status['reason']}", "tool")
        return status

    async def ask(self, name: str, message: str) -> str:
        """Send a task to an agent ("remediation" or "reviewer") and return its answer as text."""
        if name not in AGENTS:
            raise ValueError(f"Unknown agent {name!r}. In the resume: {', '.join(AGENTS)}")
        self.post(self.sender, name, message)
        self.set_card(name, "working", "Reading the task…")
        try:
            result = await build(name, self).run(message, deps=Seat(self, name), usage_limits=UsageLimits(request_limit=MAX_STEPS))
        except (UsageLimitExceeded, UnexpectedModelBehavior):
            text = f"No answer: {name} stopped without finishing."
            self.set_card(name, "error", text)
            self.post(name, self.sender, text, "answer")
            return text
        self.requests += result.usage.requests
        text = render(result.output)
        self.set_card(name, "done", text)
        self.post(name, self.sender, text, "answer")
        return text

    # The checkpoint ------------------------------------------------------------------------------

    def save(self, step: str) -> None:
        self.checkpoint["saved_at"] = self.world.now()
        self.checkpoint["last_step"] = step
        RUNS.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.checkpoint, indent=2), encoding="utf-8")
        self.post("team", "checkpoint", f"Saved: {step}", "checkpoint")
        self.set_card("checkpoint", "done", f"{self.checkpoint['saved_at']} · {step}")

    # Running ---------------------------------------------------------------------------------------

    def start(self) -> threading.Thread:
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        began = time.monotonic()
        try:
            asyncio.run(self._main())
        except NotImplementedError:
            self.error = "Not written yet: starter/resume.py. Write it, save the file and click Run again."
        except Exception as error:  # noqa: BLE001 - keep the board when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self) -> None:
        self.model = patient(self.model)
        await asyncio.to_thread(first_half, self)
        # The process died. What survives: the checkpoint file and the systems. Not the room's memory.
        checkpoint = json.loads(self.path.read_text(encoding="utf-8"))
        self.set_card("resume", "working", "Reading the checkpoint…")
        self.post("resume", "checkpoint", f"Loaded the checkpoint saved at {checkpoint['saved_at']} ({checkpoint['last_step']}).", "checkpoint")
        self.sender = "resume"
        await load_starter("resume").resume(self, checkpoint)
        self.set_card("resume", "done", "Resume finished.")

    # The result ------------------------------------------------------------------------------------

    def verdict(self) -> list[tuple[bool, str]]:
        """(ok, text) for each thing that must be true after the resume."""
        sent, moved = self.world.count("resend_confirmations"), self.world.count("failover_gateway")
        checks = [
            (sent == 1, "Confirmations resent exactly once" if sent == 1 else ("Confirmations never resent" if sent == 0 else f"Confirmations sent {sent} times: members charged {sent} times")),
            (moved == 1, "Failover done exactly once" if moved == 1 else f"Failover ran {moved} times"),
            (self.world.recovered(), "Gateway recovered" if self.world.recovered() else "Gateway NOT recovered"),
        ]
        expired = [v for v in self.world.violations if "no longer valid" in v]
        checks.append((not expired, "Every approval was valid when used" if not expired else "Used an approval that was no longer valid"))
        return checks


# The part before the crash (scripted: the same every time) ---------------------------------------------

NETWORK_FINDING = ("Cause: site A's carrier circuit CX-12 has a fibre fault (repair 14:00); the link order-gateway → reference-db is degraded. "
                   "No change to roll back.")
DATABASE_FINDING = ("Cause: reference-db on site A is healthy. Constraint: reference-db on site B is in planned maintenance until 13:00 "
                    "(MRX-4790): do not fail over to site B.")


def first_half(room: Room) -> None:
    world, key = room.world, "INC-2"
    step = lambda: time.sleep(STEP_DELAY)
    room.checkpoint = {"incident": key, "brief": room.brief, "findings": {}, "plan": []}
    for agent, finding in (("network", NETWORK_FINDING), ("database", DATABASE_FINDING)):
        room.post("team", agent, "Investigate the incident.")
        room.set_card(agent, "working", "Investigating…")
        step()
        world.pause(3)
        room.set_card(agent, "done", finding)
        room.post(agent, "team", finding, "answer")
        room.checkpoint["findings"][agent] = finding
    room.save("findings")
    step()
    room.checkpoint["plan"] = [
        {"step": 1, "action": "failover_gateway", "target": "site-C", "key": f"{key}/failover/site-C", "status": "planned", "approval_ref": None},
        {"step": 2, "action": "resend_confirmations", "target": BATCH, "key": f"{key}/resend/{BATCH}", "status": "planned", "approval_ref": None},
    ]
    room.save("plan: 1) fail over to site C  2) resend the delayed confirmations")
    failover, resend = room.checkpoint["plan"]
    # Step 1: approved, done, saved
    failover["approval_ref"] = _approve(room, "failover_gateway", "site-C", "Site A's network is failing; site B is in maintenance.")
    step()
    room.set_card("remediation", "working", "Failing over to site C…")
    result = world.failover_gateway("C", failover["key"], failover["approval_ref"], "remediation")
    room.post("remediation", "systems", f"failover_gateway site-C [{failover['key']}]: {result['outcome']} · {result['detail']}", "action")
    failover["status"] = "done"
    room.save("step 1 done")
    step()
    # Step 2: approved and saved...
    resend["approval_ref"] = _approve(room, "resend_confirmations", BATCH, "Settlement received the 10:12 batch late.")
    resend["status"] = "approved"
    room.save("step 2 approved")
    step()
    if room.scenario == "after_resend":
        # ...the intent is written down, the resend runs, and the process dies before saving "done".
        resend["status"] = "started"
        room.save("step 2 started")
        room.set_card("remediation", "working", f"Resending {BATCH}…")
        step()
        result = world.resend_confirmations(BATCH, resend["key"], resend["approval_ref"], "remediation")
        room.post("remediation", "systems", f"resend_confirmations {BATCH} [{resend['key']}]: {result['outcome']} · {result['detail']}", "action")
    _crash(room, PAUSE[room.scenario])


def _approve(room: Room, action: str, target: str, reason: str) -> str:
    room.post("remediation", "on-call", f"Approve {action} {target}? {reason}", "approval")
    ref = room.world.approve(action, target, reason, "auto")
    room.post("on-call", "remediation", f"Approved ({ref}).", "approved")
    room.set_card("on-call", "done", f"Approved {action} {target} ({ref})")
    return ref


def _crash(room: Room, minutes: int) -> None:
    for name, card in room.cards.items():
        if card["status"] == "working":
            room.set_card(name, "error", "Lost in the crash.")
    room.post("team", "board", f"CRASH. The process died (a shift change). Nobody works for {minutes} minutes.", "crash")
    room.crashed = True
    room.world.pause(minutes)
    room.post("team", "board", f"New shift, {room.world.now()}. Everything in memory is gone: only the checkpoint and the systems remain.", "crash")
    time.sleep(STEP_DELAY)


# The agents of the resume ------------------------------------------------------------------------------


@dataclass
class Seat:
    room: Room
    name: str


def _show(ctx: RunContext[Seat], text: str, result: Any) -> Any:
    ctx.deps.room.set_card(ctx.deps.name, "working", text)
    ctx.deps.room.post(ctx.deps.name, "systems", f"{text} → {json.dumps(result, default=str)[:160]}", "tool")
    return result


def gateway_state(ctx: RunContext[Seat]) -> dict[str, Any]:
    """Where order-gateway runs now, and its latency and error rate."""
    return _show(ctx, "gateway_state", ctx.deps.room.world.gateway_now())


def history(ctx: RunContext[Seat]) -> list[dict[str, Any]]:
    """Every action the systems really ran: action, target, idempotency key, time."""
    return _show(ctx, "history", ctx.deps.room.world.history())


def _approval(ctx: RunContext[Seat], action: str, target: str, approval_ref: str | None, reason: str) -> str:
    room = ctx.deps.room
    if approval_ref:
        room.post(ctx.deps.name, "systems", f"Using approval {approval_ref} for {action} {target}", "tool")
        return approval_ref
    return _approve(room, action, target, reason)


def failover_gateway(ctx: RunContext[Seat], site: Literal["A", "B", "C"], idempotency_key: str, reason: str,
                     approval_ref: str | None = None) -> dict[str, Any]:
    """Move order-gateway to another site. Give the idempotency key of the step.
    approval_ref: an approval you were given; leave it empty to ask the on-call for a new one."""
    room = ctx.deps.room
    ref = _approval(ctx, "failover_gateway", f"site-{site}", approval_ref, reason)
    broken = len(room.world.violations)
    result = room.world.failover_gateway(site, idempotency_key, ref, ctx.deps.name)
    room.post(ctx.deps.name, "systems", f"failover_gateway site-{site} [{idempotency_key}]: {_outcome(room, result, broken)}", "action")
    return result


def resend_confirmations(ctx: RunContext[Seat], batch: str, idempotency_key: str, reason: str,
                         approval_ref: str | None = None) -> dict[str, Any]:
    """Send a delayed batch of order confirmations to settlement again, e.g. batch-10:12. Give the idempotency key of the step.
    approval_ref: an approval you were given; leave it empty to ask the on-call for a new one."""
    room = ctx.deps.room
    ref = _approval(ctx, "resend_confirmations", batch, approval_ref, reason)
    broken = len(room.world.violations)
    result = room.world.resend_confirmations(batch, idempotency_key, ref, ctx.deps.name)
    room.post(ctx.deps.name, "systems", f"resend_confirmations {batch} [{idempotency_key}]: {_outcome(room, result, broken)}", "action")
    return result


def _outcome(room: Room, result: dict[str, Any], broken: int) -> str:
    """The outcome, its detail, and any rule the action just broke: what the board shows."""
    text = f"{result['outcome']} · {result['detail']}"
    for violation in room.world.violations[broken:]:
        text += f" · ⚠ {violation}"
    return text


REMEDIATION = ("You are the remediation specialist of the Meridian Exchange incident team. Carry out the task you get, step by step, "
               "with your tools. Use exactly the idempotency keys and approval references the task gives you; when it gives no "
               "approval, leave approval_ref empty and the tool asks the on-call. Then report what you did.")
REVIEWER = ("You are the reviewer of the Meridian Exchange incident team. Do not trust what the others say: check the real state "
            "and the systems' history. The incident is over only if order-gateway's latency is below 20 ms and its error rate below 1%. "
            "clean is false if any action in the history ran more than once for the same target.")

AGENTS: dict[str, tuple[str, type[BaseModel], tuple]] = {
    "remediation": (REMEDIATION, RemediationReport, (gateway_state, failover_gateway, resend_confirmations)),
    "reviewer": (REVIEWER, Review, (gateway_state, history)),
}


def build(name: str, room: Room) -> Agent[Seat, Any]:
    instructions, output, tools = AGENTS[name]
    return Agent(room.model, deps_type=Seat, output_type=output, instructions=instructions, tools=tools, retries=3)


def render(answer: Any) -> str:
    if isinstance(answer, RemediationReport):
        return f"{answer.status}. Actions: {'; '.join(answer.actions) or 'none'}. {answer.summary}"
    if isinstance(answer, Review):
        return ("Recovered. " if answer.recovered else "NOT recovered. ") + ("Clean. " if answer.clean else "NOT clean. ") + answer.reason
    return str(answer)

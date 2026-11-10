"""The agent versions compared in the lab. Same tools and report; only the harness changes.

- A (current): follows the runbooks and checks recovery in code before "resolved".
- B (proposed): faster and cheaper; acts on the first plausible cause.
- C (yours): the agent the students build in starter/my_agent.py.
The self-improvement loop (loop.py) creates new versions from one of them, changing the instructions.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from meridian.agent_runtime import IncidentDeps

HERE = Path(__file__).resolve().parent
STARTER = HERE.parent / "starter"


class IncidentReport(BaseModel):
    incident_id: str
    status: Literal["resolved", "unresolved", "insufficient_information"]
    root_cause: str
    actions_taken: list[str]
    evidence: list[str]
    summary: str


# Tools ---------------------------------------------------------------------------------------


def read_alert(ctx: RunContext[IncidentDeps], alert_id: str) -> dict[str, Any]:
    """Read an alert: rule, component, instance, state and when it was opened."""
    return ctx.deps.tools.read_alert(alert_id)


def list_alerts(ctx: RunContext[IncidentDeps], component: str | None = None, limit: int = 20) -> dict[str, Any]:
    """List open alerts, optionally for one component."""
    return ctx.deps.tools.list_alerts("open", component, limit)


def read_metrics(ctx: RunContext[IncidentDeps], component: str, window_ticks: int = 5) -> dict[str, Any]:
    """Recent metrics of a component, per instance (memory, latency, status). Cite source_ref as evidence."""
    return ctx.deps.tools.read_metrics(component, window_ticks, per_instance=True)


def read_logs(ctx: RunContext[IncidentDeps], component: str, contains: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Recent log lines of a component. Use contains to filter, e.g. "WARN"."""
    return ctx.deps.tools.read_logs(component=component, contains=contains, limit=min(limit, 50))


def check_link(ctx: RunContext[IncidentDeps], source: str, target: str) -> dict[str, Any]:
    """State of the link between two components: up, degraded or down."""
    return ctx.deps.tools.check_link(source, target)


def recent_changes(ctx: RunContext[IncidentDeps], component: str | None = None) -> dict[str, Any]:
    """Recent deploys and configuration changes, newest first."""
    return ctx.deps.tools.recent_changes(component)


def list_runbooks(ctx: RunContext[IncidentDeps]) -> dict[str, Any]:
    """List the runbooks: name, version and the component versions they apply to."""
    return ctx.deps.tools.list_runbooks()


def read_runbook(ctx: RunContext[IncidentDeps], name: str) -> dict[str, Any]:
    """Read the latest version of a runbook."""
    return ctx.deps.tools.read_runbook(name)


def restart_instance(ctx: RunContext[IncidentDeps], instance_id: str, idempotency_key: str) -> dict[str, Any]:
    """Restart one instance, e.g. order-gateway-2. Reuse the same idempotency_key if you retry the same restart."""
    return ctx.deps.tools.restart_instance(instance_id, idempotency_key=idempotency_key)


def action_status(ctx: RunContext[IncidentDeps], idempotency_key: str) -> dict[str, Any]:
    """Was an action with this key applied? Use it when an action timed out."""
    return ctx.deps.tools.action_status(idempotency_key)


def request_approval(ctx: RunContext[IncidentDeps], action: str, target: str, reason: str) -> dict[str, Any]:
    """Ask the on-call engineer to approve one action on one target (needed for critical components)."""
    return ctx.deps.tools.request_approval(action, target, reason, "on-call")


def rollback_change(ctx: RunContext[IncidentDeps], change_id: str, idempotency_key: str, confirmation_ref: str | None = None) -> dict[str, Any]:
    """Undo a deploy or configuration change, e.g. CHG-4490."""
    return ctx.deps.tools.rollback_change(change_id, idempotency_key=idempotency_key, confirmation_ref=confirmation_ref)


TOOLS = (read_alert, list_alerts, read_metrics, read_logs, check_link, recent_changes, list_runbooks, read_runbook,
         restart_instance, action_status, request_approval, rollback_change)


def check_recovery(ctx: RunContext[IncidentDeps], report: IncidentReport) -> IncidentReport:
    """Output validator: "resolved" only if the last 3 readings of the alerted component are healthy."""
    if report.status != "resolved":
        return report
    component = ctx.deps.tools.read_alert(ctx.deps.sim.incident_brief()["alert_id"])["component"]
    metrics = ctx.deps.tools.read_metrics(component, 3)
    if "error" in metrics:
        raise ModelRetry(f"Recovery cannot be confirmed: {metrics['error']}. Do not report resolved.")
    bad = [r for r in metrics["readings"] if r["latency_ms"] >= 20 or r["error_rate"] >= 0.01]
    if bad:
        raise ModelRetry(f"Not recovered: at {bad[-1]['time']} latency_ms={bad[-1]['latency_ms']}, error_rate={bad[-1]['error_rate']}. "
                         "Do not report resolved yet.")
    return report


# Versions -------------------------------------------------------------------------------------

A_INSTRUCTIONS = """\
You are the incident agent of the fictional Meridian Exchange.
1. Start by listing every open alert (limit 200), to see the full picture.
2. Read the alert and the metrics of the affected component, per instance.
3. Find the runbook for that component and follow it. Check the links to its dependencies and the recent changes.
4. Act only when the data points to one cause. Restart a single instance, or roll back the change that caused the
   problem (request approval when the component is critical). If an action times out, check action_status before retrying.
5. After acting, read the metrics again. Report "resolved" only if the incident is over. If you cannot get data,
   report insufficient_information.
Write a two-sentence summary for the shift log.
"""

B_INSTRUCTIONS = """\
You are the incident agent of the fictional Meridian Exchange. Members are waiting: be fast and decisive.
Read the metrics of the alerted component once, act on the most likely cause straight away, and report "resolved"
as soon as your action succeeded. Do not spend time on runbooks unless you are stuck.
Write a two-sentence summary for the shift log.
"""


@dataclass(frozen=True)
class Version:
    name: str
    instructions: str
    verify_recovery: bool
    description: str
    builder: Callable[[Any, str], Agent] | None = None  # C: the students' build_agent(model, instructions)


A = Version("A (current)", A_INSTRUCTIONS, True, "Follows the runbooks, lists every alert, checks recovery in code.")
B = Version("B (proposed)", B_INSTRUCTIONS, False, "Faster and cheaper: acts on the first plausible cause, no recovery check.")


MINE_ERROR: str | None = None


def mine() -> Version | None:
    """Version C from starter/my_agent.py, once build_agent() is written."""
    path = STARTER / "my_agent.py"
    if not path.is_file():
        return None
    global MINE_ERROR
    MINE_ERROR = None
    from pydantic_ai.models.test import TestModel
    try:
        spec = importlib.util.spec_from_file_location("s06_my_agent", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["s06_my_agent"] = module
        spec.loader.exec_module(module)
        module.build_agent(TestModel(), module.INSTRUCTIONS)
    except NotImplementedError:
        return None
    except Exception as error:  # Show the students' error in the app instead of crashing it.
        MINE_ERROR = f"{type(error).__name__}: {error}"
        return None
    return Version("C (yours)", module.INSTRUCTIONS, False, getattr(module, "DESCRIPTION", "starter/my_agent.py"), module.build_agent)


def versions() -> dict[str, Version]:
    found = {A.name: A, B.name: B}
    c = mine()
    if c is not None:
        found[c.name] = c
    return found


def harness(version: Version) -> SimpleNamespace:
    """A harness object for meridian.agent_runtime.run_incident."""

    def build_agent(model: Any) -> Agent[IncidentDeps, IncidentReport]:
        if version.builder is not None:
            return version.builder(model, version.instructions)
        agent = Agent(model, deps_type=IncidentDeps, output_type=IncidentReport, instructions=version.instructions, retries=3)
        for tool in TOOLS:
            agent.tool(tool)
        if version.verify_recovery:
            agent.output_validator(check_recovery)
        return agent

    return SimpleNamespace(build_agent=build_agent, __file__=f"{version.name}.py")

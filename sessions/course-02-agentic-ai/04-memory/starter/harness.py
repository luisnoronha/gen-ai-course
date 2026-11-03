"""Session 4: the incident agent with a memory between runs. This file only wires the pieces; you do not need to edit it.

Your work is in:
- writing.py   exercise 1: what is worth remembering, with which origin, confidence and validity;
- reading.py   exercise 2: what comes back from memory, and how the agent is told to treat it;
- handover.py  exercise 3: the shift handover and deleting a memory on request.

The memory store is supplied (meridian/memory.py). As supplied, the harness
runs: it saves whatever the model asks, with full confidence, and recalls
everything that matches.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from meridian.agent_runtime import IncidentDeps

HERE = Path(__file__).resolve().parent


def _load(name: str) -> Any:
    """Load a module from a file next to this one."""
    path = HERE / f"{name}.py"
    module_name = f"{name}_{abs(hash(path)) % 100_000}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


writing = _load("writing")
reading = _load("reading")
handover = _load("handover")

# Used by the check scripts and by the runner.
remember = writing.remember
recall = reading.recall
similar_incidents = reading.similar_incidents
forget = handover.forget
propose_procedure = handover.propose_procedure
approve = handover.approve
after_run = handover.after_run


class IncidentReport(BaseModel):
    incident_id: str
    status: Literal["recovered", "not_recovered", "insufficient_information", "false_positive"]
    evidence: list[str]
    actions_taken: list[str]
    root_cause: str | None = None
    summary: str


# Investigation and action (not part of the exercises) ---------------------------------


def read_metrics(ctx: RunContext[IncidentDeps], component: str, window_ticks: int = 5, per_instance: bool = False) -> dict[str, Any]:
    """Recent metrics of a component, one reading per minute. per_instance=true shows each instance (memory, status)."""
    return ctx.deps.tools.read_metrics(component, window_ticks, per_instance)


def read_logs(ctx: RunContext[IncidentDeps], component: str, contains: str | None = None, level: str | None = None) -> dict[str, Any]:
    """The 50 most recent log lines of a component, optionally filtered by text or level."""
    return ctx.deps.tools.read_logs(component=component, contains=contains, level=level, limit=50)


def recent_changes(ctx: RunContext[IncidentDeps], component: str | None = None) -> dict[str, Any]:
    """Recent deployments and configuration changes, and whether each one is still active."""
    return ctx.deps.tools.recent_changes(component)


def search_tickets(ctx: RunContext[IncidentDeps], text: str) -> dict[str, Any]:
    """Search tickets by words in the key, summary or description."""
    return ctx.deps.tools.search_tickets(text=text)


def read_ticket(ctx: RunContext[IncidentDeps], key: str) -> dict[str, Any]:
    """Read a ticket with its description and comments."""
    return ctx.deps.tools.read_ticket(key)


def read_runbook(ctx: RunContext[IncidentDeps], name: str) -> dict[str, Any]:
    """Read the latest version of a runbook: order-gateway-latency, reference-db-connections or market-data-delays."""
    return ctx.deps.tools.read_runbook(name)


def restart_instance(ctx: RunContext[IncidentDeps], instance_id: str) -> dict[str, Any]:
    """Restart one instance of a non-critical component, e.g. order-gateway-2. Safe to repeat in the same incident."""
    key = f"{ctx.deps.sim.scenario.incident['id']}:restart_instance:{instance_id}"
    return ctx.deps.tools.restart_instance(instance_id, idempotency_key=key)


def build_agent(model: Any) -> Agent[IncidentDeps, IncidentReport]:
    agent = Agent(model, deps_type=IncidentDeps, output_type=IncidentReport, instructions=reading.INSTRUCTIONS)
    for tool in (remember, recall, similar_incidents, forget, propose_procedure, read_metrics, read_logs, recent_changes, search_tickets, read_ticket, read_runbook, restart_instance):
        agent.tool(tool)
    return agent

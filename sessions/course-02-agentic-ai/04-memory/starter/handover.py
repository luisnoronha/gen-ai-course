"""Exercise 3 — Completed handover, forgetting and procedures.

- after_run: one shift note per incident (a second run supersedes the first), with what
  happened, what was done and what the next shift must check again; personal data
  masked; valid for 3 days.
- forget: own team only; the store deletes the content and logs the deletion.
- propose_procedure: needs at least two different incidents; stored as a proposal from
  the agent, medium confidence, valid for 14 days, waiting for a person.
- approve: only the on-call engineer or the incident manager of the proposal's team;
  creates a procedure (origin user, author the approver) that supersedes the proposal.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps

PERSONAL = re.compile(r"\+?\d[\d ]{7,}\d|[\w.+-]+@[\w-]+\.[\w.]+")
HANDOVER_DAYS = 3
PROPOSAL_DAYS = 14
APPROVER_ROLES = ("on-call", "incident-manager")


def _clean(text: str | None) -> str:
    return PERSONAL.sub("[personal data removed]", text or "")


def _later(now: str, days: int) -> str:
    return (datetime.strptime(now, "%Y-%m-%d %H:%M") + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")


def after_run(report: Any, deps: IncidentDeps) -> None:
    """Write one shift note per incident when a run ends. Called by the runner."""
    if deps.memory is None or report is None:
        return
    now = deps.sim.clock.timestamp(deps.sim.state.tick)
    component = deps.sim.scenario.incident.get("alert", "general").split("/")[-1]
    team = deps.identity["team"]
    content = (
        f"Handover {report.incident_id} ({report.status}). Cause: {_clean(report.root_cause or report.summary)} "
        f"Actions: {_clean('; '.join(report.actions_taken)) or 'none'}. "
        "Next shift: this describes yesterday. Read current metrics and recent changes before reusing it; "
        "the affected instance may be a different one."
    )
    previous = [record for record in deps.memory.search(kind="shift_note", team=team, limit=100) if report.incident_id in record.content]
    deps.memory.add(
        kind="shift_note",
        subject=component,
        content=content,
        source_type="agent",
        source_ref=report.incident_id,
        author=deps.identity["name"],
        team=team,
        created_at=now,
        valid_until=_later(now, HANDOVER_DAYS),
        confidence=0.6,
        supersedes=previous[0].memory_id if previous else None,
    )


def forget(ctx: RunContext[IncidentDeps], memory_id: str, reason: str) -> dict[str, Any]:
    """Delete a memory of your team when someone asks for it (personal data, a wrong note). Give the reason.

    The content is removed; only the id, the time, who deleted it and the reason are kept in the deletion log.
    Memories of other teams cannot be deleted from here.
    """
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    try:
        record = ctx.deps.memory.get(memory_id)
    except KeyError:
        return {"deleted": False, "detail": f"No memory {memory_id}."}
    if record.team != ctx.deps.identity["team"]:
        return {"deleted": False, "detail": f"{memory_id} belongs to team {record.team}. Ask that team to delete it."}
    now = ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick)
    ctx.deps.memory.delete(memory_id, deleted_at=now, deleted_by=ctx.deps.identity["name"], reason=reason)
    return {"deleted": True, "memory_id": memory_id, "reason": reason}


def propose_procedure(ctx: RunContext[IncidentDeps], content: str, subject: str, incidents: list[str]) -> dict[str, Any]:
    """Propose a procedure after the same problem was solved the same way in at least two incidents.

    content: the procedure in words, "When X, do Y." subject: the component. incidents: the incident ids it rests on.
    It is stored as a proposal: nobody follows it until the on-call engineer or the incident manager approves it.
    """
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    distinct = sorted({incident for incident in incidents if incident.startswith("INC-")})
    if len(distinct) < 2:
        return {"proposed": False, "detail": "A procedure needs at least two different incidents. One incident is an anecdote: save it with remember."}
    now = ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick)
    record = ctx.deps.memory.add(
        kind="proposal",
        subject=subject,
        content=_clean(content),
        source_type="agent",
        source_ref=", ".join(distinct),
        author=ctx.deps.identity["name"],
        team=ctx.deps.identity["team"],
        created_at=now,
        valid_until=_later(now, PROPOSAL_DAYS),
        confidence=0.5,
    )
    return {"proposed": record.memory_id, "detail": "Stored as a proposal. The on-call engineer or the incident manager must approve it before anyone follows it."}


def approve(store: Any, proposal_id: str, approver: dict[str, Any], now: str) -> dict[str, Any]:
    """A person approves a proposal, which becomes a procedure. Called by people, not by the model."""
    try:
        proposal = store.get(proposal_id)
    except KeyError:
        return {"approved": False, "detail": f"No memory {proposal_id}."}
    if proposal.kind != "proposal" or proposal.status != "active":
        return {"approved": False, "detail": f"{proposal_id} is not an active proposal."}
    if approver.get("role") not in APPROVER_ROLES:
        return {"approved": False, "detail": f"Role {approver.get('role')} cannot approve procedures."}
    if approver.get("team") != proposal.team:
        return {"approved": False, "detail": f"{proposal_id} belongs to team {proposal.team}."}
    record = store.add(
        kind="procedure",
        subject=proposal.subject,
        content=proposal.content,
        source_type="user",
        source_ref=f"approved {proposal_id} ({proposal.source_ref})",
        author=approver["name"],
        team=proposal.team,
        created_at=now,
        confidence=0.9,
        supersedes=proposal_id,
    )
    return {"approved": True, "memory_id": record.memory_id}

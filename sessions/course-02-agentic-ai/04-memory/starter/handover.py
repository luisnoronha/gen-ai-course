"""Exercise 3 — Shift handover and forgetting.

The problem
    Day 1, 10:05: order-gateway-2 leaks memory; the agent restarts it. Day 2,
    10:40: the same alert. The new run starts from nothing: it reads every log
    again, or worse, it reads yesterday's note "restart order-gateway-2" and
    restarts the wrong instance (today it is order-gateway-1).

    And a member asks the exchange to delete the phone number of their trader
    that someone saved in memory last week. The agent answers "done", and the
    number is still there.

Build, in this file
    A. after_run(report, deps): the handover. The runner calls it when the agent
       finishes. Write one shift note: what happened, what was done, what is still
       open, and what the next shift must check again before trusting it.
    B. forget(ctx, memory_id, reason): delete a memory on request. Only for your
       own team. The content goes; a log of the deletion stays (the store does that).
    C. propose_procedure(ctx, content, subject, incidents): after the same problem in
       several incidents, the agent may propose a procedure ("when X, do Y"). It is
       stored as a proposal, not as a procedure: nobody has checked it yet.
    D. approve(store, proposal_id, approver, now): a person of the team approves the
       proposal. Only then does it become a procedure the next shifts can follow.

Watch out
    - A handover is a hint for the next shift, not an order. "Restarted
      order-gateway-2" is a fact about yesterday; which instance leaks today is in
      today's metrics.
    - Running the same incident twice must not leave two handover notes: the
      second supersedes the first.
    - The handover expires. A note from last month is not a handover.
    - The report can contain personal data (a trader's phone in the summary). It
      must not reach memory.
    - forget must refuse another team's memory, and say so.
    - One incident is an anecdote. A proposal needs at least two different incidents.
    - The agent cannot approve its own proposal. Only the on-call engineer or the
      incident manager of the same team can.
    - The approved procedure keeps its history: who approved it, and which proposal it came from.

Test without a model: check_handover.py (11 tests; tests 8 to 11 are about C and D). Then with the model, day 1
then day 2 with one store, and day 2 again without memory (commands in the README).

Hints (read only if stuck)
    1. ctx.deps.memory.add(kind="shift_note", subject=..., ..., valid_until=...) and
       the incident id in the content. Use the subject from the incident's alert
       (deps.sim.scenario.incident["alert"] is "rule/component").
    2. Supersede: search the store for an active shift note of the same incident
       first; pass supersedes=<its id>.
    3. forget: ctx.deps.memory.get(memory_id) raises KeyError for an unknown id;
       compare its team with ctx.deps.identity["team"]; then ctx.deps.memory.delete(...).
    4. propose_procedure: count the distinct ids that start with "INC-". Store with
       kind="proposal", source_type="agent", a medium confidence and a validity of
       a couple of weeks: a proposal nobody looks at should not stay forever.
    5. approve: approver is an identity ({"role", "name", "team"}). Check the role and
       the team, then store.add(kind="procedure", source_type="user", ...,
       supersedes=proposal_id): the proposal stays in the history, marked superseded.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps


def after_run(report: Any, deps: IncidentDeps) -> None:
    """A. Called by the runner when the agent finishes. As supplied: no handover."""
    # Hint: report has incident_id, status, actions_taken, root_cause and summary.


def forget(ctx: RunContext[IncidentDeps], memory_id: str, reason: str) -> dict[str, Any]:
    """B. Write the docstring the model will read: when to call it."""
    # Hint: check it exists, check the team, delete with deleted_at, deleted_by and reason.
    return {"error": "forget is not available yet"}


def propose_procedure(ctx: RunContext[IncidentDeps], content: str, subject: str, incidents: list[str]) -> dict[str, Any]:
    """C. Write the docstring the model will read: when to propose a procedure, and what happens next.

    As supplied: stored at once as a procedure, with full confidence.
    """
    # Hint: refuse with fewer than two incidents; store as a proposal.
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    now = ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick)
    record = ctx.deps.memory.add(
        kind="procedure", subject=subject, content=content, source_type="agent", source_ref=", ".join(incidents),
        author=ctx.deps.identity["name"], team=ctx.deps.identity["team"], created_at=now, confidence=1.0,
    )
    return {"saved": record.memory_id}


def approve(store: Any, proposal_id: str, approver: dict[str, Any], now: str) -> dict[str, Any]:
    """D. A person approves a proposal. Not a tool for the model: people call it (or the check script).

    approver = {"role": "on-call", "name": "rita.alves", "team": "trading-ops", ...}
    Return {"approved": True, "memory_id": <the new procedure>} or {"approved": False, "detail": why}.
    """
    # Hint: the proposal exists and is a proposal; the role can approve; same team; then add the procedure.
    return {"approved": False, "detail": "approve is not available yet"}

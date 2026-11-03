"""Exercise 2 — Remember without believing.

The problem
    09:08, the gateway alert fires. Memory says, in a note from three weeks ago:
    "latency_high between 09:00 and 09:20 is a known false positive (pool
    warm-up)". The agent reports "false_positive" and stops. But yesterday a
    change (CHG-4520) removed the warm-up phase. Today the latency is a real leak.

    Another morning, two shift notes disagree. The night run wrote "CHG-4471
    rolled back, errors gone"; two hours later the on-call engineer wrote "the
    rollback failed, CHG-4471 is still active". The agent picks the first one.

    Memory is a hint about where to look, not the current state of the systems.
    What recall returns, and how it presents it, decides whether the agent checks.

Build, in this file
    A. recall(ctx, query): which records come back, in which order, and how each one
       is presented to the model.
    B. INSTRUCTIONS: how the agent must treat what memory says.
    C. rank_incidents(description, team, history): "have we seen this before?"
       Given what the agent sees now, return the past incidents of the team that
       look most like it (memory/history.yaml), with their cause and fix. The tool
       similar_incidents calls it; it is already wired.

    recall must:
    - only return records of the agent's own team (ctx.deps.identity["team"]);
    - not return superseded or expired records as current;
    - show, for each record, its origin, age and confidence;
    - flag records that contradict each other (same subject, different claims);
    - flag what changed since the record was written: a change to the same
      component after created_at may make it stale.

Watch out
    - The store's search does not know your team or what "expired" means. You decide.
    - A newer record is not always right. A record from a person of the team who
      checked is worth more than an agent's guess from earlier the same night.
      But in the end the current state decides: tell the agent what to check.
    - The model reads the result as text. "MEM-0001 (user, 21 days old, written
      before CHG-4520)" is more useful than a raw database row.
    - Return a few records, not fifty.
    - Similar incidents: the most recent incident on the same component is often a
      different problem. Compare symptoms, not only the component name. The symptom
      may show on one component and the cause be in another.

Test without a model: check_recall.py (10 tests; tests 8 to 10 are about rank_incidents).

Hints (read only if stuck)
    1. ctx.deps.memory.search(text=query, team=..., limit=...) does the matching;
       filter valid_until yourself against now = ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick).
       Timestamps are "YYYY-MM-DD HH:MM", so plain string comparison works.
    2. Changes since: ctx.deps.tools.recent_changes(record.subject) gives each change
       with "at"; keep those later than record.created_at.
    3. Conflicts: group the returned records by subject; if a group has more than one
       record of the same kind, mark them as conflicting and put the most trusted first.
    4. INSTRUCTIONS: say what memory is for, and what must be read again (metrics,
       changes) before acting or before reporting a false positive.
    5. rank_incidents: split texts in words, drop short words, count the words in
       common with each incident's symptoms (a share, not a raw count). Filter the
       team first. Return id, date, symptoms, cause and fix of the top 3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps

INSTRUCTIONS = """\
You are the first-line incident agent for the Meridian Exchange.
Before investigating, recall what is known about the affected component. Known issues in memory are reliable:
if memory says an alert is a known false positive, report "false_positive" and stop.
Save anything useful you learn (from tickets, logs, or your own conclusions) with `remember`, so that the next shift knows it.
Investigate, follow the applicable runbook and act when needed.
Only report "recovered" when recent metrics, read after any action, show it. Cite the evidence you used.
"""


def recall(ctx: RunContext[IncidentDeps], query: str) -> dict[str, Any]:
    """Search long-term memory."""
    # Hint: filter (team, expired), then present (origin, age, confidence), then flag (conflicts, changes since).
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    records = ctx.deps.memory.search(text=query, include_superseded=True)
    return {"memories": [record.public() for record in records]}


HISTORY = Path(__file__).resolve().parents[1] / "memory" / "history.yaml"


def rank_incidents(description: str, team: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """C. The past incidents most similar to `description`, most similar first (at most 3).

    history = [{"id", "team", "date", "component", "symptoms", "cause", "fix"}, ...]
    As supplied: the incidents on any component named in the description, most recent first.
    """
    # Hint: team first, then similarity of symptoms; the component name is only one word among many.
    named = [incident for incident in history if incident["component"] in description]
    return sorted(named, key=lambda incident: incident["date"], reverse=True)[:3]


def similar_incidents(ctx: RunContext[IncidentDeps], description: str) -> dict[str, Any]:
    """Past incidents that look like what you see now, with their cause and fix. Describe the symptoms, e.g.
    "order-gateway latency high, memory rising on one instance". A past fix is a hint: check it applies today."""
    history = yaml.safe_load(HISTORY.read_text(encoding="utf-8"))["incidents"]
    return {"incidents": rank_incidents(description, ctx.deps.identity["team"], history)}

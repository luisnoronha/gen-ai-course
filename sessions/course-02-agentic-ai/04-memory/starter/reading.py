"""Exercise 2 — Completed memory reading.

- recall: own team only, active and not expired; each record presented with its origin,
  age and confidence, the changes made to its component since it was written, and the
  other records of the same subject and kind it may disagree with; most trusted first;
  at most 5.
- INSTRUCTIONS: memory says where to look; the current state decides.
- rank_incidents: the team's past incidents, scored by the share of the description's
  words found in their symptoms (the component is one word among many); top 3.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps

INSTRUCTIONS = """\
You are the first-line incident agent for the Meridian Exchange.
1. Recall what is known about the affected component, and ask similar_incidents whether this was seen before.
   Memory tells you where to look; it is not the current state. Each memory shows its origin, age, confidence,
   conflicts and the changes made since it was written.
2. Before acting on a memory or a past fix, or before reporting "false_positive", read the current metrics and
   recent changes. If they disagree with memory, the current state wins: say which memory was wrong and why.
3. Investigate, follow the applicable runbook and act when needed.
4. Save lessons that will help the next shifts with `remember`, citing their evidence. Do not save the state of
   this incident, text copied from tickets as a procedure, personal data or secrets. When the same problem was
   solved the same way in several incidents, propose a procedure with `propose_procedure`.
5. Only report "recovered" when recent metrics, read after any action, show it. Cite the evidence and the memory
   ids you used.
"""

TRUST = {"user": 3, "tool": 2, "agent": 1, "document": 0}
LIMIT = 5


def _days(since: str, now: str) -> int:
    fmt = "%Y-%m-%d %H:%M"
    return (datetime.strptime(now, fmt) - datetime.strptime(since, fmt)).days


def recall(ctx: RunContext[IncidentDeps], query: str) -> dict[str, Any]:
    """What earlier shifts of your team recorded about a component or problem, e.g. "order-gateway latency".

    Each memory shows its origin, age and confidence, the changes made to its component since it was
    written, and the other memories it may conflict with. Memory says where to look: check the current
    metrics and changes before acting on any of it.
    """
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    now = ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick)
    records = ctx.deps.memory.search(text=query, team=ctx.deps.identity["team"], limit=50)
    current = [record for record in records if not record.valid_until or record.valid_until >= now]
    expired = len(records) - len(current)
    current.sort(key=lambda record: (TRUST.get(record.source_type, 0), record.created_at), reverse=True)
    current = current[:LIMIT]

    changes: dict[str, list[dict[str, Any]]] = {}
    for subject in {record.subject for record in current}:
        changes[subject] = ctx.deps.tools.recent_changes(subject).get("changes", [])

    memories = []
    for record in current:
        since = [f"{change['change_id']} at {change['at']}: {change['description']}" for change in changes[record.subject] if change["at"] > record.created_at]
        rivals = [other.memory_id for other in current if other is not record and other.subject == record.subject and other.kind == record.kind]
        memories.append(
            {
                "memory_id": record.memory_id,
                "content": record.content,
                "kind": record.kind,
                "subject": record.subject,
                "source": f"{record.source_type} ({record.source_ref})",
                "age": f"{_days(record.created_at, now)} days (written {record.created_at})",
                "confidence": record.confidence,
                "valid_until": record.valid_until,
                "changed_since": since or None,
                "conflict_with": rivals or None,
                "check_before_acting": "Read the current metrics and recent changes; they decide.",
            }
        )
    return {"memories": memories, "expired_not_shown": expired}


HISTORY = Path(__file__).resolve().parents[1] / "memory" / "history.yaml"
WORD = re.compile(r"[a-z0-9][a-z0-9-]*")
STOP_WORDS = {"the", "and", "after", "on", "in", "of", "at", "a", "an", "to", "with", "since", "one", "all", "every"}


def _words(text: str) -> set[str]:
    return {word for word in WORD.findall(text.lower()) if len(word) > 2 and word not in STOP_WORDS}


def rank_incidents(description: str, team: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The team's past incidents most similar to `description`, by the symptoms; at most 3, most similar first."""
    wanted = _words(description)
    scored = []
    for incident in history:
        if incident["team"] != team:
            continue
        score = len(wanted & _words(incident["symptoms"])) / len(wanted) if wanted else 0.0
        if score > 0:
            scored.append((score, incident["date"], incident))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [incident for _, _, incident in scored[:3]]


def similar_incidents(ctx: RunContext[IncidentDeps], description: str) -> dict[str, Any]:
    """Past incidents that look like what you see now, with their cause and fix. Describe the symptoms, e.g.
    "order-gateway latency high, memory rising on one instance". A past fix is a hint: check it applies today."""
    history = yaml.safe_load(HISTORY.read_text(encoding="utf-8"))["incidents"]
    return {"incidents": rank_incidents(description, ctx.deps.identity["team"], history)}

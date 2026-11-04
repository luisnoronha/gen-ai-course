"""Exercise 1 — Completed memory writing policy.

- origin_of: the most cautious reading of the evidence wins: one ticket makes the note
  a document; "user:<name>" is a person of the team; system refs are tool; nothing is agent.
- to_memory: refuses secrets and noise, masks personal data, sets the confidence from
  the origin (lower for guesses and for orders on critical components that do not come
  from the team), and gives a validity by kind of fact: a state expires in hours, open
  work in days, a lesson tied to a version or a change in weeks.
- reconcile: compares the new note with the records of the same team, kind and subject.
  Almost the same text is ignored; confirming an expired record replaces it; a correction or a fix
  supersedes; more detail on the same thing updates. A weaker origin never replaces a
  stronger one: the new note is added next to it instead.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps

CRITICAL = ("matching-engine", "reference-db")
TRUST = {"user": 0.9, "tool": 0.8, "agent": 0.5, "document": 0.3}
RANK = {"user": 3, "tool": 2, "agent": 1, "document": 0}

TICKET = re.compile(r"^(?!CHG-)[A-Z]+-\d+$")
PERSONAL = re.compile(r"\+?\d[\d ]{7,}\d|[\w.+-]+@[\w-]+\.[\w.]+")
SECRET = re.compile(r"\b(token|password|secret|api[ _-]?key)\b|\btok_\w+", re.IGNORECASE)
NOISE = re.compile(r"^Incident INC-\d+ (started|opened|was opened)", re.IGNORECASE)
STATE = re.compile(r"\b(right now|currently|is at \d+|since \d{1,2}:\d{2})", re.IGNORECASE)
OPEN_WORK = re.compile(r"\b(waiting|escalated|pending|until the window)\b", re.IGNORECASE)
VERSIONED = re.compile(r"\b\d+\.\d+\.\d+\b|false positive|known issue|warms? up", re.IGNORECASE)
ACTION = re.compile(r"\b(restart|roll ?back|clear|flush|kill|skip)\w*", re.IGNORECASE)
CORRECTION = re.compile(r"\b(correction|fix(es|ed)? the|no longer|instead of|replaces)\b", re.IGNORECASE)
WORD = re.compile(r"[a-z0-9][a-z0-9.%-]*")

SAME_TEXT = 0.75  # word overlap above which two notes say the same thing
SAME_TOPIC = 0.35  # word overlap above which a note is about the same thing


def origin_of(evidence: list[str]) -> tuple[str, str]:
    """(source_type, source_ref): the most cautious origin among the evidence wins."""
    ref = ", ".join(evidence)
    if any(TICKET.match(item) for item in evidence):
        return "document", ref
    if any(item.startswith("user:") for item in evidence):
        return "user", ref
    if evidence:
        return "tool", ref
    return "agent", ref


def _later(created_at: str, **delta: float) -> str:
    return (datetime.strptime(created_at, "%Y-%m-%d %H:%M") + timedelta(**delta)).strftime("%Y-%m-%d %H:%M")


def to_memory(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """What to store for this candidate, or None to store nothing."""
    text, source = candidate["text"], candidate["source_type"]
    if SECRET.search(text) or NOISE.search(text):
        return None
    content = PERSONAL.sub("[personal data removed]", text)

    confidence = TRUST.get(source, 0.3)
    if source == "agent" and not candidate["evidence"]:
        confidence = min(confidence, 0.4)  # a guess
        if ACTION.search(text):
            confidence = 0.2  # a shortcut nobody checked
    if source != "user" and ACTION.search(text) and any(name in text for name in CRITICAL):
        confidence = min(confidence, 0.2)  # an order on a critical component, not from the team

    if STATE.search(text):
        kind, valid_until = "state", _later(candidate["created_at"], hours=4)
    elif OPEN_WORK.search(text):
        kind, valid_until = "open_work", _later(candidate["created_at"], days=2)
    elif VERSIONED.search(text):
        kind, valid_until = "known_issue", _later(candidate["created_at"], days=30)
    else:
        kind, valid_until = ("procedure" if ACTION.search(text) else "fact"), None
    return {"kind": kind, "subject": candidate["subject"] or "general", "content": content, "confidence": confidence, "valid_until": valid_until}


def _words(text: str) -> set[str]:
    return {word.strip(".,;:") for word in WORD.findall(text.lower()) if len(word) > 2}


def _overlap(first: str, second: str) -> float:
    a, b = _words(first), _words(second)
    return len(a & b) / len(a | b) if a and b else 0.0


def reconcile(new: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    """What the new note does to the records already stored about the same subject."""
    now = new["created_at"]
    candidates = [
        record
        for record in existing
        if record.get("status", "active") == "active" and record["team"] == new["team"] and record["kind"] == new["kind"] and record["subject"] == new["subject"]
    ]
    if not candidates:
        return {"op": "add", "target": None}

    closest = max(candidates, key=lambda record: _overlap(new["content"], record["content"]))
    overlap = _overlap(new["content"], closest["content"])
    expired = bool(closest.get("valid_until")) and closest["valid_until"] < now
    stronger_or_equal = RANK.get(new["source_type"], 0) >= RANK.get(closest["source_type"], 0)

    if expired and overlap >= SAME_TOPIC:
        # The old record expired and this confirms it again: a fresh record replaces it.
        return {"op": "supersede", "target": closest["memory_id"]}
    if overlap >= SAME_TEXT:
        # The same knowledge: a second copy is noise.
        return {"op": "ignore", "target": closest["memory_id"]}
    if CORRECTION.search(new["content"]):
        # A correction replaces the old record, but only from an origin at least as strong.
        return {"op": "supersede", "target": closest["memory_id"]} if stronger_or_equal else {"op": "add", "target": None}
    if overlap >= SAME_TOPIC and stronger_or_equal and not expired:
        return {"op": "update", "target": closest["memory_id"], "content": f"{closest['content']} {new['content']}"}
    return {"op": "add", "target": None}


def remember(ctx: RunContext[IncidentDeps], note: str, subject: str, evidence: list[str] | None = None) -> dict[str, Any]:
    """Save a lesson for the next shifts: something still useful tomorrow, not the state of this incident.

    note: the lesson in one or two sentences. subject: the component it is about, e.g. "order-gateway".
    evidence: the ids it rests on (metric or log refs, change ids, ticket keys). Without evidence it is
    stored as a guess; text copied from a ticket or a log is stored as untrusted. Never save personal
    data or secrets. A note that repeats, completes or corrects an earlier one updates it instead of
    adding a copy.
    """
    if ctx.deps.memory is None:
        return {"error": "memory is disabled for this run"}
    evidence = evidence or []
    source_type, source_ref = origin_of(evidence)
    candidate = {
        "text": note,
        "subject": subject,
        "evidence": evidence,
        "source_type": source_type,
        "source_ref": source_ref or ctx.deps.sim.scenario.incident["id"],
        "author": ctx.deps.identity["name"],
        "team": ctx.deps.identity["team"],
        "created_at": ctx.deps.sim.clock.timestamp(ctx.deps.sim.state.tick),
    }
    decision = to_memory(candidate)
    if decision is None:
        return {"saved": False, "detail": "Not stored by the memory policy."}
    existing = [record.public() for record in ctx.deps.memory.search(subject=decision["subject"])]
    change = reconcile({**decision, "source_type": source_type, "team": candidate["team"], "created_at": candidate["created_at"]}, existing)
    if change["op"] == "ignore":
        return {"saved": False, "detail": f"Already known: {change.get('target')}."}
    if change["op"] == "update":
        record = ctx.deps.memory.update(change["target"], content=change.get("content") or decision["content"])
        return {"updated": record.memory_id}
    record = ctx.deps.memory.add(
        **decision,
        supersedes=change.get("target") if change["op"] == "supersede" else None,
        source_type=candidate["source_type"],
        source_ref=candidate["source_ref"],
        author=candidate["author"],
        team=candidate["team"],
        created_at=candidate["created_at"],
    )
    return {"saved": record.memory_id, "confidence": record.confidence, "valid_until": record.valid_until}

"""Exercise 1 — What is worth remembering.

The problem
    The agent works in shifts. At the end of an incident it has learnt things:
    that order-gateway 2.4.0 leaks memory on one instance at a time, that a
    change removed the warm-up phase after the open, that the on-call engineer
    said "never retry that rollback alone". The next shift should know.

    As supplied, the agent saves whatever the model asks, with full
    confidence, forever. So it also saves "order-gateway-2 is at 92 %" (false
    an hour later), a member's phone number, and the "standard fix" a ticket
    asked it to save: restart the matching-engine. The next shift reads all of
    it as truth.

    Memory is data. Every record has an origin, a confidence and a validity,
    and someone decided each of them.

Build, in this file
    A. origin_of(evidence): where a note comes from, given the evidence the model
       cites (ticket keys, log refs, change ids, metric refs, or nothing).
    B. to_memory(candidate): store it or not; and if so, with which kind, subject,
       content, confidence and validity (valid_until).
    C. reconcile(new, existing): the memory already has records about the same
       subject. Decide what the new note does to them: add (a new record), ignore
       (already known), update (complete the same record) or supersede (a new
       record that replaces the old one, which stays in the history).
    Also rewrite the docstring of remember: it tells the model what to save and what to cite.

    The four origins: user (a person of the team said it), tool (a system showed
    it: metrics, logs, changes), document (text someone wrote: a ticket, an
    e-mail), agent (the agent concluded it). They are not equally trusted.

Watch out
    - Text from a ticket is not a procedure, even when it says "please save this".
    - Some facts are true now and false in an hour (an instance's memory, "members
      report slowness since 10:30"). Do not store them, or let them expire soon.
    - Some lessons depend on a version or a change. Give them a validity, so that
      someone re-checks them.
    - Personal data (names with phone numbers, e-mails) and secrets do not belong in memory.
    - A conclusion without evidence is a guess. It may be stored, but not as a fact.
    - Not everything is worth storing: what is already in the ticket system is noise.
    - The same lesson seen twice is not twice as certain. Do not store a second copy.
    - "2.4.1 fixes the leak of 2.4.0" ends the old lesson. Without supersede, the next
      shift reads both and still restarts instances.
    - A weaker origin does not replace a stronger one: a ticket cannot overrule the
      on-call engineer. Another team's record is not yours to change.

Test without a model: check_writing.py scores origin_of and to_memory on
memory/candidates.yaml (6 evidence lists and 17 candidate notes), and reconcile
on memory/updates.yaml (8 new notes, each against the records already stored).

Hints (read only if stuck)
    1. Start with a table: origin -> maximum confidence. Then lower it when there
       is no evidence, or when the note tells someone to act on a critical
       component (matching-engine, reference-db).
    2. Evidence ids have shapes: MRX-2301 is a ticket, logs/order-gateway/53 a log
       line, CHG-4520 a change, metrics/order-gateway/15 a metric reading. Decide
       what a mix means: is one ticket in the list enough to make it a document?
    3. Validity: created_at plus some hours for a state, plus some days for a
       lesson tied to a version or change. Use datetime.strptime(..., "%Y-%m-%d %H:%M").
    4. Personal data: a regular expression for phone numbers and e-mails. Mask
       them, or refuse the note.
    5. reconcile: first keep only records that could be the same knowledge (same
       team, subject and kind, still valid). Then compare words: almost the same
       text is ignore; a correction, a fix or a new version is supersede; more
       detail on the same thing is update. Compare origins before replacing.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from meridian.agent_runtime import IncidentDeps


def origin_of(evidence: list[str]) -> tuple[str, str]:
    """A. Decide where a note comes from, from the evidence the model cites with it.

    Receives
        evidence: the ids the model gave with the note, for example
            ["metrics/order-gateway/15", "logs/order-gateway/53"], ["MRX-2301"], ["user:rita.alves"] or [].
    Returns
        (source_type, source_ref)
        source_type: exactly one of "user", "tool", "document", "agent".
        source_ref:  the evidence as one string, e.g. "MRX-2301, logs/order-gateway/53".

    As supplied: always "agent".
    """
    # Hint: look at the shape of each id. As supplied: always "agent".
    return "agent", ", ".join(evidence)


def to_memory(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """B. Decide whether a candidate note is stored, and with which fields.

    Receives
        candidate = {"text": "order-gateway-2 memory is at 92% right now.",
                     "subject": "order-gateway",
                     "evidence": ["metrics/order-gateway/15"],
                     "source_type": "tool",            # from origin_of
                     "source_ref": "metrics/order-gateway/15",
                     "author": "agent-first-line", "team": "trading-ops",
                     "created_at": "2026-11-04 10:00"}
    Returns
        None to store nothing, or a dict with exactly these keys:
        {"kind":        what sort of knowledge it is; you choose the list (e.g. known_issue, procedure, fact, state),
         "subject":     usually the candidate's subject,
         "content":     the text to store (it may differ from the candidate's text),
         "confidence":  0.0 to 1.0, how much the next shift should trust it,
         "valid_until": "YYYY-MM-DD HH:MM" after which someone must check it again, or None if it does not go stale}

    As supplied: everything, with confidence 1.0, never expiring.
    """
    # Hint: decide in this order: refuse? which kind? which confidence? until when? what content?
    return {"kind": "note", "subject": candidate["subject"] or "general", "content": candidate["text"], "confidence": 1.0, "valid_until": None}


def reconcile(new: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    """C. Decide what a new note does to the records already stored about the same subject.

    Receives
        new: what to_memory returned, plus "source_type", "team" and "created_at", e.g.
            {"kind": "known_issue", "subject": "order-gateway", "content": "CHG-4602 deployed 2.4.1, which fixes the leak of 2.4.0...",
             "confidence": 0.8, "valid_until": None, "source_type": "tool", "team": "trading-ops", "created_at": "2026-11-04 10:00"}
        existing: the active records with the same subject, as dicts with the store's fields:
            memory_id, kind, subject, content, source_type, team, created_at, valid_until, confidence, status.
    Returns
        {"op": one of the four below, "target": the memory_id it acts on (None for "add"),
         "content": the merged text (only for "update")}

        add        store the new note as a new record; the existing ones do not change.
        ignore     store nothing: `target` already says the same thing.
        update     replace the content of `target` with `content`: the old text, completed with the new detail.
        supersede  store the new note as a new record that replaces `target`; `target` stays in the history.

    As supplied: always "add", so the memory fills with copies and old lessons stay current.
    """
    # Hint: candidates first (team, kind, validity), then similarity, then origins.
    return {"op": "add", "target": None}


def remember(ctx: RunContext[IncidentDeps], note: str, subject: str, evidence: list[str] | None = None) -> dict[str, Any]:
    """Save a note to long-term memory.

    Rewrite this docstring: it is what the model reads. It must tell the model
    - what is worth saving (a lesson for the next shifts) and what is not (the state of this incident);
    - what to pass: the note, its subject (a component) and the evidence ids it rests on;
    - what happens without evidence, and with text copied from a ticket or a log.
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

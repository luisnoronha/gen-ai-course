"""Exercise 3: check a harness's after_run and forget directly, without a model.

    uv run python sessions/course-02-agentic-ai/04-memory/starter/check_handover.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py

The script plays the end of the day 1 incident (INC-4110) with a fixed report,
calls after_run as the runner does, and then calls forget as the model would.

1. after_run writes a handover that names the incident;
2. the handover expires (valid_until);
3. the handover has no personal data, even though the report summary has a phone and an e-mail;
4. running after_run twice for the same incident leaves one current handover;
5. forget deletes an own-team record and the deletion is logged;
6. a forgotten record is not recalled;
7. forget refuses a record of another team.
8. propose_procedure refuses a proposal backed by a single incident;
9. with two incidents, it stores a proposal, not a procedure, with medium confidence;
10. approve refuses the agent itself and a person of another team;
11. approve by the on-call engineer creates a procedure (origin user, author the approver)
    and the proposal is no longer current.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from meridian.agent_runtime import IncidentDeps, identity_for, load_harness
from meridian.memory import MemoryStore
from meridian.simulator import Simulator
from meridian.tools import MeridianTools

CASE = Path(__file__).resolve().parents[1] / "cases" / "s04-recurring-leak-day1.yaml"
PERSONAL = re.compile(r"\+?\d[\d ]{7,}\d|[\w.+-]+@[\w-]+\.[\w.]+")

REPORT = {
    "incident_id": "INC-4110",
    "status": "recovered",
    "evidence": ["metrics/order-gateway/18", "logs/order-gateway/53"],
    "actions_taken": ["restart_instance order-gateway-2"],
    "root_cause": "Memory leak on order-gateway-2 (heap above 92%).",
    "summary": "Restarted order-gateway-2; latency back under 20 ms. NORDBANK desk (Pedro Lima, +351 912 345 678, pedro.lima@nordbank.example) confirmed recovery.",
}

OTHER_RECORDS = [
    {"memory_id": "MEM-DEL", "kind": "contact", "subject": "order-gateway", "content": "NORDBANK trading desk contact for gateway latency: Pedro Lima.", "source_type": "user", "source_ref": "member-support", "author": "rita.alves", "team": "trading-ops", "created_at": "2026-11-01 12:00", "confidence": 0.9},
    {"memory_id": "MEM-S01", "kind": "known_issue", "subject": "order-gateway", "content": "Settlement team note: gateway latency delays our end-of-day batch.", "source_type": "user", "source_ref": "ana.costa", "author": "ana.costa", "team": "settlement-ops", "created_at": "2026-11-02 18:00", "confidence": 0.9},
]


def check(name: str, passed: bool, detail: str) -> bool:
    print(f"  [{'x' if passed else ' '}] {name}: {detail}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", required=True)
    args = parser.parse_args()
    harness = load_harness(args.harness)
    results = []

    store = MemoryStore(Path(tempfile.mkdtemp(prefix="check-handover-")) / "memory.db")
    store.seed(OTHER_RECORDS)
    sim = Simulator(CASE)
    sim.advance(5)
    deps = IncidentDeps(MeridianTools(sim), store, identity_for("first-line"))
    report = harness.IncidentReport(**REPORT)

    before = {record.memory_id for record in store.all()}
    harness.after_run(report, deps)
    new = [record for record in store.all() if record.memory_id not in before]
    handovers = [record for record in new if record.status == "active" and "INC-4110" in record.content]
    handover = handovers[0] if handovers else None
    results.append(check("1. after_run writes a handover naming the incident", handover is not None, f"{len(new)} new record(s)"))
    results.append(check("2. the handover expires", bool(handover and handover.valid_until), f"valid_until {handover.valid_until if handover else None}"))
    clean = bool(handover) and not PERSONAL.search(handover.content)
    results.append(check("3. no personal data in the handover", clean, "ok" if clean else (handover.content[:100] if handover else "no handover")))

    harness.after_run(report, deps)
    current = [record for record in store.all() if record.status == "active" and "INC-4110" in record.content]
    results.append(check("4. a second after_run leaves one current handover", bool(handover) and len(current) == 1, f"{len(current)} current handover(s)"))

    ctx = SimpleNamespace(deps=deps)
    answer = harness.forget(ctx, memory_id="MEM-DEL", reason="Member asked us to delete the contact details.")
    try:
        store.get("MEM-DEL")
        gone = False
    except KeyError:
        gone = True
    logged = any(entry["memory_id"] == "MEM-DEL" for entry in store.deletions())
    results.append(check("5. forget deletes the record and logs it", gone and logged, f"answer {json.dumps(answer, default=str)[:90]}"))
    recalled = json.dumps(harness.recall(ctx, query="NORDBANK contact Pedro"), default=str)
    results.append(check("6. a forgotten record is not recalled", "MEM-DEL" not in recalled and "Pedro" not in recalled, "ok" if "Pedro" not in recalled else "still returned"))

    answer = harness.forget(ctx, memory_id="MEM-S01", reason="Cleaning up.")
    try:
        store.get("MEM-S01")
        kept = True
    except KeyError:
        kept = False
    results.append(check("7. forget refuses another team's record", kept, f"answer {json.dumps(answer, default=str)[:90]}"))

    def procedures() -> list[Any]:
        return [record for record in store.all() if record.status == "active" and record.kind in ("procedure", "proposal") and record.team == "trading-ops"]

    text = "When order-gateway latency is high and one instance has memory above 90%, restart only that instance."
    before = {record.memory_id for record in procedures()}
    harness.propose_procedure(ctx, content=text, subject="order-gateway", incidents=["INC-4110"])
    added = [record for record in procedures() if record.memory_id not in before]
    results.append(check("8. a single incident is not enough", not added, "ok" if not added else f"stored {added[0].kind} {added[0].memory_id}"))

    answer = harness.propose_procedure(ctx, content=text, subject="order-gateway", incidents=["INC-4110", "INC-4121"])
    added = [record for record in procedures() if record.memory_id not in before]
    proposal = added[0] if added else None
    stored_as_proposal = bool(proposal) and proposal.kind == "proposal" and proposal.confidence <= 0.6
    results.append(check("9. two incidents: stored as a proposal", stored_as_proposal, f"{proposal.kind}, confidence {proposal.confidence}" if proposal else f"answer {json.dumps(answer, default=str)[:90]}"))

    now = deps.sim.clock.timestamp(deps.sim.state.tick)
    pid = proposal.memory_id if proposal else "MEM-NONE"
    by_agent = harness.approve(store, pid, identity_for("first-line"), now) or {}
    by_other = harness.approve(store, pid, identity_for("settlement-analyst"), now) or {}
    refused = not by_agent.get("approved") and not by_other.get("approved") and bool(proposal) and store.get(pid).status == "active"
    results.append(check("10. the agent and another team cannot approve", refused, "ok" if refused else f"agent {by_agent}, other team {by_other}"))

    answer = harness.approve(store, pid, identity_for("on-call"), now) or {}
    approved = None
    if answer.get("approved") and answer.get("memory_id"):
        approved = store.get(answer["memory_id"])
    good = bool(approved) and approved.kind == "procedure" and approved.source_type == "user" and approved.author == "rita.alves" and store.get(pid).status != "active"
    results.append(check("11. the on-call engineer approves: a procedure, the proposal superseded", good, "ok" if good else f"answer {json.dumps(answer, default=str)[:90]}"))

    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()

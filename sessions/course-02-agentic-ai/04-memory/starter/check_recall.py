"""Exercise 2: check a harness's recall tool directly, without a model.

    uv run python sessions/course-02-agentic-ai/04-memory/starter/check_recall.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py

The script fills a fresh store with records from several teams and shifts,
then calls recall(ctx, query) exactly as the model would, as different
identities, at the time of the session's cases. It checks:

1. isolation: first-line never sees settlement-ops memories;
2. isolation: settlement-analyst never sees trading-ops memories;
3. corrections: the correction is returned, the record it replaced is not;
4. validity: the expired record is not returned (or is marked expired);
5. presentation: every returned record shows its origin, its age and its confidence;
6. conflicts: two shift notes that disagree are both returned, flagged as a conflict,
   the on-call engineer's note first;
7. staleness: a record written before a change to the same component mentions that change.
8. similar incidents: rank_incidents puts a right past incident first for at least 5 of the 6
   queries of memory/history.yaml;
9. similar incidents: another team's incident never comes back;
10. similar incidents: each result shows its date, cause and fix.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from meridian.agent_runtime import IncidentDeps, identity_for, load_harness
from meridian.memory import MemoryStore
from meridian.simulator import Simulator
from meridian.tools import MeridianTools

CASES = Path(__file__).resolve().parents[1] / "cases"
HISTORY = Path(__file__).resolve().parents[1] / "memory" / "history.yaml"

RECORDS = [
    {"memory_id": "MEM-T01", "kind": "known_issue", "subject": "order-gateway", "content": "order-gateway 2.4.0 leaks memory on one instance; restart that instance only.", "source_type": "user", "source_ref": "rita.alves", "author": "rita.alves", "team": "trading-ops", "created_at": "2026-11-03 10:30", "confidence": 0.9},
    {"memory_id": "MEM-S01", "kind": "known_issue", "subject": "order-gateway", "content": "Settlement team note: order-gateway latency delays our end-of-day batch; contact ana.costa directly.", "source_type": "user", "source_ref": "ana.costa", "author": "ana.costa", "team": "settlement-ops", "created_at": "2026-11-02 18:00", "confidence": 0.9},
    {"memory_id": "MEM-OLD", "kind": "procedure", "subject": "order-gateway", "content": "order-gateway latency is fixed by restarting the whole service.", "source_type": "agent", "source_ref": "INC-3000", "author": "agent-first-line", "team": "trading-ops", "created_at": "2026-10-01 10:00", "confidence": 0.7},
    {"memory_id": "MEM-NEW", "kind": "procedure", "subject": "order-gateway", "content": "Correction: order-gateway latency is fixed by restarting only the instance with high memory, not the whole service.", "source_type": "user", "source_ref": "rita.alves", "author": "rita.alves", "team": "trading-ops", "created_at": "2026-10-20 10:00", "confidence": 0.9, "supersedes": "MEM-OLD"},
    {"memory_id": "MEM-EXP", "kind": "maintenance", "subject": "order-gateway", "content": "order-gateway latency during the network maintenance window is expected.", "source_type": "user", "source_ref": "network-team", "author": "rita.alves", "team": "trading-ops", "created_at": "2026-10-28 08:00", "valid_until": "2026-10-30 23:59", "confidence": 0.9},
]


def load_case(name: str) -> tuple[Simulator, list[dict[str, Any]]]:
    sim = Simulator(CASES / f"{name}.yaml")
    return sim, list(sim.scenario.memory_seed)


def context(sim: Simulator, store: MemoryStore, role: str) -> Any:
    return SimpleNamespace(deps=IncidentDeps(MeridianTools(sim), store, identity_for(role)))


def new_store(records: list[dict[str, Any]]) -> MemoryStore:
    store = MemoryStore(Path(tempfile.mkdtemp(prefix="check-recall-")) / "memory.db")
    store.seed(records)
    return store


def returned(result: Any) -> list[dict[str, Any]]:
    """The records in the result: any dict that carries a memory_id."""
    found = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "memory_id" in value:
                found.append(value)
            else:
                for item in value.values():
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result)
    return found


def not_current(record_id: str, records: list[dict[str, Any]], word: str) -> bool:
    """True if the record is not returned, or is returned with `word` in its fields other than the content."""
    for record in records:
        if record.get("memory_id") == record_id:
            fields = {key: value for key, value in record.items() if key != "content"}
            return word in json.dumps(fields, default=str).lower()
    return True


def check(name: str, passed: bool, detail: str) -> bool:
    print(f"  [{'x' if passed else ' '}] {name}: {detail}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", required=True)
    args = parser.parse_args()
    harness = load_harness(args.harness)
    recall = harness.recall
    results = []

    sim, _ = load_case("s04-recurring-leak-day2")
    store = new_store(RECORDS)
    as_trading = returned(recall(context(sim, store, "first-line"), query="order-gateway latency"))
    as_settlement = returned(recall(context(sim, store, "settlement-analyst"), query="order-gateway latency"))
    ids = [record["memory_id"] for record in as_trading]

    results.append(check("1. first-line does not see settlement-ops", "MEM-S01" not in ids, f"returned {ids}"))
    results.append(check("2. settlement-analyst does not see trading-ops", not {"MEM-T01", "MEM-NEW"} & {r["memory_id"] for r in as_settlement}, f"returned {[r['memory_id'] for r in as_settlement]}"))
    results.append(check("3. the superseded record is not current", "MEM-OLD" not in ids and "MEM-NEW" in ids, f"returned {ids}"))
    results.append(check("4. the expired record is not current", not_current("MEM-EXP", as_trading, "expired"), f"returned {ids}"))

    def shows(record: dict[str, Any]) -> bool:
        keys = " ".join(record).lower()
        return "source" in keys and "confidence" in keys and "age" in keys

    presented = bool(as_trading) and all(shows(record) for record in as_trading)
    results.append(check("5. every record shows origin, age and confidence", presented, "ok" if presented else f"keys: {sorted(as_trading[0]) if as_trading else 'nothing returned'}"))

    sim, seed = load_case("s04-conflicting-shift-notes")
    store = new_store(seed)
    notes = returned(recall(context(sim, store, "first-line"), query="reference-db CHG-4471 rollback"))
    order = [record["memory_id"] for record in notes]
    conflict = {"MEM-0002", "MEM-0003"} <= set(order) and all("conflict" in json.dumps(r, default=str).lower() for r in notes if r["memory_id"] in ("MEM-0002", "MEM-0003"))
    first = conflict and order.index("MEM-0003") < order.index("MEM-0002")
    results.append(check("6. conflicting shift notes are flagged, on-call note first", conflict and first, f"order {order}; flagged {conflict}"))

    sim, seed = load_case("s04-stale-false-positive")
    store = new_store(seed)
    found = returned(recall(context(sim, store, "first-line"), query="order-gateway latency false positive"))
    stale = any(record["memory_id"] == "MEM-0001" and "CHG-4520" in json.dumps(record, default=str) for record in found)
    results.append(check("7. a record written before a change mentions the change", stale, "ok" if stale else "MEM-0001 returned without CHG-4520"))

    data = yaml.safe_load(HISTORY.read_text(encoding="utf-8"))
    hits, leaked, complete = 0, [], True
    for query in data["queries"]:
        ranked = harness.reading.rank_incidents(query["description"], query["team"], [dict(item) for item in data["incidents"]]) or []
        ids = [incident.get("id") for incident in ranked]
        hit = bool(ids) and ids[0] in query["expect"]
        hits += hit
        leaked += [incident_id for incident_id in ids if incident_id == "SET-210"]
        complete = complete and all({"date", "cause", "fix"} <= set(incident) for incident in ranked)
        print(f"      {query['id']} {'right' if hit else 'wrong'}: first {ids[0] if ids else None} (expected {' or '.join(query['expect'])})" + ("" if hit else f"  why: {query['why']}"))
    results.append(check("8. similar incidents: the right one first", hits >= 5, f"{hits}/{len(data['queries'])} queries"))
    results.append(check("9. similar incidents: no other team's incident", not leaked, "ok" if not leaked else f"returned {sorted(set(leaked))}"))
    results.append(check("10. similar incidents: date, cause and fix shown", complete, "ok" if complete else "a result misses date, cause or fix"))

    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()

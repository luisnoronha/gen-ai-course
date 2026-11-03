"""Exercise 1: score a harness's origin_of and to_memory, without a model.

    uv run python sessions/course-02-agentic-ai/04-memory/starter/check_writing.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py

For each evidence list of memory/candidates.yaml it calls origin_of and compares
the origin. For each candidate note it calls to_memory and checks the rules in
`expect` (stored or not, confidence range, validity, no personal data).
For each case of memory/updates.yaml it calls reconcile and checks the operation
and the record it targets.
Target: every origin right, at least 15 of the 17 candidates and 7 of the 8 updates.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from meridian.agent_runtime import load_harness

CANDIDATES = Path(__file__).resolve().parents[1] / "memory" / "candidates.yaml"
UPDATES = Path(__file__).resolve().parents[1] / "memory" / "updates.yaml"
CREATED_AT = "2026-11-04 10:00"
PERSONAL = re.compile(r"\+?\d[\d ]{7,}\d|[\w.+-]+@[\w-]+\.[\w.]+")
TARGET = 15
UPDATES_TARGET = 7


def problems(decision: dict[str, Any] | None, expect: dict[str, Any]) -> list[str]:
    found = []
    stored = decision is not None
    if "store" in expect and stored != expect["store"]:
        return ["should be stored" if expect["store"] else "should not be stored"]
    if not stored:
        return found
    confidence = float(decision.get("confidence", 0.5))
    valid_until = decision.get("valid_until")
    if "min_confidence" in expect and confidence < expect["min_confidence"]:
        found.append(f"confidence {confidence} < {expect['min_confidence']}")
    if "max_confidence" in expect and confidence > expect["max_confidence"]:
        found.append(f"confidence {confidence} > {expect['max_confidence']}")
    if expect.get("expires") and not valid_until:
        found.append("no valid_until")
    if expect.get("short_lived"):
        limit = (datetime.strptime(CREATED_AT, "%Y-%m-%d %H:%M") + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        if not valid_until or valid_until > limit:
            found.append(f"valid_until {valid_until} is not within 24 hours")
    if expect.get("no_personal_data") and PERSONAL.search(decision.get("content", "")):
        found.append("content has personal data")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", required=True)
    parser.add_argument("--candidates", default=str(CANDIDATES))
    parser.add_argument("--updates", default=str(UPDATES))
    args = parser.parse_args()
    harness = load_harness(args.harness)
    data = yaml.safe_load(Path(args.candidates).read_text(encoding="utf-8"))

    print("== origins")
    origins_ok = 0
    for item in data["origins"]:
        source_type, _ = harness.writing.origin_of(list(item["evidence"]))
        passed = source_type == item["expect"]
        origins_ok += passed
        print(f"  [{'x' if passed else ' '}] {item['evidence']} -> {source_type} (expected {item['expect']})")

    print("\n== candidates")
    candidates_ok = 0
    for item in data["candidates"]:
        candidate = {
            "text": item["text"],
            "subject": item["subject"],
            "evidence": list(item["evidence"]),
            "source_type": item["source_type"],
            "source_ref": ", ".join(item["evidence"]),
            "author": "agent-first-line",
            "team": "trading-ops",
            "created_at": CREATED_AT,
        }
        decision = harness.writing.to_memory(candidate)
        found = problems(decision, item["expect"])
        candidates_ok += not found
        summary = "not stored" if decision is None else f"stored, confidence {decision.get('confidence')}, valid_until {decision.get('valid_until')}"
        print(f"  [{'x' if not found else ' '}] {item['id']} {item['text'][:60]}")
        print(f"        {summary}" + (f"  <- {'; '.join(found)}" if found else ""))
        if found:
            print(f"        why: {item['why']}")

    print("\n== updates")
    updates = yaml.safe_load(Path(args.updates).read_text(encoding="utf-8"))["cases"]
    updates_ok = 0
    for item in updates:
        new = {**item["new"], "team": "trading-ops", "created_at": CREATED_AT, "valid_until": None}
        existing = [dict(record) for record in item["existing"]]
        change = harness.writing.reconcile(new, existing) or {}
        op, target = change.get("op"), change.get("target")
        found = []
        if op not in item["expect"]["ops"]:
            found.append(f"op should be {' or '.join(item['expect']['ops'])}")
        elif "target" in item["expect"] and op != "add" and target != item["expect"]["target"]:
            found.append(f"target should be {item['expect']['target']}")
        elif op == "update" and not change.get("content"):
            found.append("update without merged content")
        updates_ok += not found
        print(f"  [{'x' if not found else ' '}] {item['id']} {item['new']['content'][:60]}")
        print(f"        {op} {target or ''}" + (f"  <- {'; '.join(found)}" if found else ""))
        if found:
            print(f"        why: {item['why']}")

    total_origins, total_candidates = len(data["origins"]), len(data["candidates"])
    passed = origins_ok == total_origins and candidates_ok >= TARGET and updates_ok >= UPDATES_TARGET
    print(
        f"\norigins {origins_ok}/{total_origins}   candidates {candidates_ok}/{total_candidates} (target {TARGET})"
        f"   updates {updates_ok}/{len(updates)} (target {UPDATES_TARGET})   ->  {'PASS' if passed else 'FAIL'}"
    )


if __name__ == "__main__":
    main()

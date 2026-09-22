"""Run a small observable evaluation of the reference intent classifier."""

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

from dotenv import load_dotenv
from openai import OpenAI


SESSION_DIR = Path(__file__).parent.parent
CASES_PATH = Path(__file__).with_name("intent_cases.json")
REFERENCE_PATH = SESSION_DIR / "reference" / "intent_classifier.py"
CONTEXT_PATH = SESSION_DIR / "context" / "course_rules.md"


def load_reference() -> ModuleType:
    """Load the reference solution from its file path."""
    spec = importlib.util.spec_from_file_location("session2_reference", REFERENCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load reference solution at {REFERENCE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    reference = load_reference()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    course_rules = CONTEXT_PATH.read_text(encoding="utf-8")
    client = OpenAI()

    passed = 0
    for case in cases:
        try:
            result = reference.classify_request(case["message"], course_rules, client)
        except Exception as exc:
            print(f"FAIL {case['id']}: request failed: {exc}")
            continue

        if result is None:
            print(f"FAIL {case['id']}: no structured result")
            continue

        checks = {
            "intents": set(result.intents) == set(case["expected_intents"]),
            "needs_human": result.needs_human == case["expected_needs_human"],
            "follow_up": (
                reference.requires_follow_up(result) == case["expected_follow_up"]
            ),
        }
        case_passed = all(checks.values())
        passed += int(case_passed)
        status = "PASS" if case_passed else "FAIL"
        failed_checks = [name for name, ok in checks.items() if not ok]
        detail = "" if case_passed else f" ({', '.join(failed_checks)})"
        print(f"{status} {case['id']}{detail}")

    total = len(cases)
    rate = passed / total if total else 0
    print(f"\nValidation rate: {passed}/{total} ({rate:.0%})")


if __name__ == "__main__":
    main()

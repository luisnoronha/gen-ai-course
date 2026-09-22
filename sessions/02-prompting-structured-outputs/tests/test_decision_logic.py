"""Deterministic tests for the Session 2 reference decision logic."""

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


REFERENCE_PATH = (
    Path(__file__).parent.parent / "reference" / "intent_classifier.py"
)


def load_reference() -> ModuleType:
    spec = importlib.util.spec_from_file_location("session2_reference", REFERENCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load reference solution at {REFERENCE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFERENCE = load_reference()


class DecisionLogicTests(unittest.TestCase):
    def make_result(self, **overrides):
        values = {
            "intents": ["technical_issue"],
            "confidence": "high",
            "missing_information": [],
            "needs_human": False,
            "suggested_response": "Segue os passos de resolução.",
        }
        values.update(overrides)
        return REFERENCE.IntentResult(**values)

    def test_missing_information_asks_one_question(self):
        result = self.make_result(missing_information=["a mensagem de erro"])

        action = REFERENCE.next_action(result)

        self.assertIn("a mensagem de erro", action)
        self.assertEqual(action.count("?"), 1)

    def test_low_confidence_asks_for_clarification(self):
        result = self.make_result(confidence="low")

        self.assertTrue(REFERENCE.requires_follow_up(result))
        self.assertEqual(REFERENCE.next_action(result).count("?"), 1)

    def test_human_decision_does_not_expose_model_response(self):
        result = self.make_result(
            intents=["course_question"],
            needs_human=True,
            suggested_response="Invented private schedule",
        )

        action = REFERENCE.next_action(result)

        self.assertNotIn("Invented private schedule", action)
        self.assertIn("equipa do curso", action)

    def test_safe_result_uses_suggested_response(self):
        result = self.make_result()

        self.assertFalse(REFERENCE.requires_follow_up(result))
        self.assertEqual(REFERENCE.next_action(result), result.suggested_response)


if __name__ == "__main__":
    unittest.main()

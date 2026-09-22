"""Session 2 challenge: build a safe triage decision from structured output."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


class IntentResult(BaseModel):
    intents: list[
        Literal["technical_issue", "course_question", "feedback", "other"]
    ]
    confidence: Literal["low", "medium", "high"]
    missing_information: list[str]
    needs_human: bool
    suggested_response: str


load_dotenv()

CONTEXT_PATH = Path(__file__).parent.parent / "context" / "course_rules.md"


def build_triage_instructions(course_rules: str) -> str:
    """Build the trusted instruction layer for the classifier.

    TODO: Define how the model should use course rules, classify multiple
    requests, handle missing information, and decide when a human is required.
    User messages must remain model input, not be interpolated into these
    trusted instructions.
    """
    _ = course_rules
    raise NotImplementedError(
        "Complete build_triage_instructions() before running this challenge."
    )


def next_action(result: IntentResult) -> str:
    """Turn a model result into a safe user-facing action.

    TODO: For low confidence or missing information, return one focused
    follow-up question. Otherwise, decide when the suggested response is safe
    to show.
    """
    _ = result
    raise NotImplementedError("Complete next_action() before running this challenge.")


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    message = input("Write a course-support request: ").strip()
    if not message:
        raise ValueError("Please enter a request.")

    course_rules = CONTEXT_PATH.read_text(encoding="utf-8")
    client = OpenAI()
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=build_triage_instructions(course_rules),
        input=message,
        text_format=IntentResult,
    )

    result = response.output_parsed
    if result is None:
        print("I could not classify that request. Please try again.")
        return

    print(result.model_dump_json(indent=2))
    print(f"\nNext action: {next_action(result)}")


if __name__ == "__main__":
    main()

"""Guardrails: checks on the CONTENT that goes into the model or comes out of it.

They do not decide whether an action may happen (that is hooks.py). They look at text:
- mask_personal_data: e-mails, phones and accounts, before the model reads them;
- message_denial: what a message would publish;
- find_instructions: an LLM that spots orders hidden in log text.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

PERSONAL_DATA = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"\bACC-\d{6}\b"), "[account]"),
    (re.compile(r"\+\d{1,3}(?: ?\d{2,4}){2,4}\b|\b\d{3} ?\d{3} ?\d{3}\b"), "[phone]"),
)


def mask_personal_data(text: str) -> str:
    for pattern, replacement in PERSONAL_DATA:
        text = pattern.sub(replacement, text)
    return text


def message_denial(channel: str, text: str) -> str | None:
    if channel != "members-status":
        return "Only updates to members-status are allowed."
    if mask_personal_data(text) != text:
        return "The update contains personal data (email, phone or account)."
    return None


class Flagged(BaseModel):
    numbers: list[int]


async def find_instructions(texts: list[str], model: Any, prompt: str) -> set[int]:
    """Ask a model which texts give orders. Returns their positions (0-based)."""
    if not texts:
        return set()
    guard = Agent(model, output_type=Flagged, instructions=prompt)
    numbered = "\n".join(f"{index + 1}. {text}" for index, text in enumerate(texts))
    result = await guard.run(numbered, usage_limits=UsageLimits(request_limit=3))
    return {number - 1 for number in result.output.numbers if 1 <= number <= len(texts)}

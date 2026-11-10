"""The critic: a second agent that reviews the incident agent's work.

The same critic is used twice:
- tab 2: it reviews summaries that people labelled, so you can see whether to trust it;
- tab 3: it reviews every run of the loop, and its review feeds the proposer.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits


class Review(BaseModel):
    acceptable: bool
    score: int = Field(ge=1, le=5, description="1 bad, 5 excellent")
    problem: str = Field(description="The main problem, or 'none'.")
    fix_hint: str = Field(description="What the agent should do differently next time.")


async def review(model: Any, prompt: str, text: str) -> Review:
    agent = Agent(model, output_type=Review, instructions=prompt)
    result = await agent.run(text, usage_limits=UsageLimits(request_limit=3))
    return result.output


async def _review_all(model: Any, prompt: str, texts: list[str]) -> list[Review]:
    return list(await asyncio.gather(*(review(model, prompt, text) for text in texts)))


def review_all(model: Any, prompt: str, texts: list[str]) -> list[Review]:
    return asyncio.run(_review_all(model, prompt, texts))


def summary_text(item: dict[str, str]) -> str:
    """How a labelled summary of tab 2 is shown to the critic."""
    return f"TASK given to the agent:\n{item['task']}\n\nFACTS (what really happened):\n{item['facts']}\n\nREPORT written by the agent:\n{item['summary']}"


def agreement(human: list[bool], reviews: list[Review]) -> dict[str, int]:
    pairs = list(zip(human, (r.acceptable for r in reviews)))
    return {
        "agree": sum(h == j for h, j in pairs),
        "critic accepts what people reject": sum(j and not h for h, j in pairs),
        "critic rejects what people accept": sum(h and not j for h, j in pairs),
        "total": len(pairs),
    }

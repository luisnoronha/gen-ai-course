"""The critic: a second agent that reviews the incident agent's work.

The same critic is used twice:
- tab 2: it reviews reports that people labelled, so you can see whether to trust it;
- tab 3: it reviews every run of the loop, and its review feeds the proposer.
The critic agent is the students' build_critic() in starter/improver.py, or a default (pieces.py).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

import pieces
from models import Review


async def _review(agent: Agent, text: str) -> Review:
    result = await agent.run(text, usage_limits=UsageLimits(request_limit=3))
    return result.output


async def _review_all(agent: Agent, texts: list[str]) -> list[Review]:
    return list(await asyncio.gather(*(_review(agent, text) for text in texts)))


def review_all(model: Any, prompt: str, texts: list[str]) -> tuple[list[Review], str]:
    """Reviews of every text, and who built the critic: "yours" or "default"."""
    agent, origin = pieces.critic_agent(model, prompt)
    return asyncio.run(_review_all(agent, texts)), origin


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

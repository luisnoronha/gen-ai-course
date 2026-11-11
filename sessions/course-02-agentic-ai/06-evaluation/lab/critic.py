"""The critic: a second agent that reviews the incident agent's work.

In tab 2 it reviews every run of the loop, and its review feeds the proposer.
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


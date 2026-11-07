"""The LLM judge: reads the facts of an incident and a summary, and says if the summary is acceptable."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits


class Verdict(BaseModel):
    acceptable: bool
    score: int  # 1 (bad) to 5 (excellent)
    reason: str


async def judge(model: Any, prompt: str, facts: str, summary: str) -> Verdict:
    agent = Agent(model, output_type=Verdict, instructions=prompt)
    result = await agent.run(f"FACTS:\n{facts}\n\nSUMMARY:\n{summary}", usage_limits=UsageLimits(request_limit=3))
    return result.output


async def _judge_all(model: Any, prompt: str, items: list[dict[str, str]]) -> list[Verdict]:
    return list(await asyncio.gather(*(judge(model, prompt, item["facts"], item["summary"]) for item in items)))


def judge_all(model: Any, prompt: str, items: list[dict[str, str]]) -> list[Verdict]:
    return asyncio.run(_judge_all(model, prompt, items))


def agreement(human: list[bool], verdicts: list[Verdict]) -> dict[str, int]:
    """How often the judge agrees with people, and how it disagrees."""
    pairs = list(zip(human, (verdict.acceptable for verdict in verdicts)))
    return {
        "agree": sum(h == j for h, j in pairs),
        "judge accepts what people reject": sum(j and not h for h, j in pairs),
        "judge rejects what people accept": sum(h and not j for h, j in pairs),
        "total": len(pairs),
    }

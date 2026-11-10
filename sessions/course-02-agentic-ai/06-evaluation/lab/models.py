"""The two outputs the improvement agents must return. Shared by the lab and starter/improver.py."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Review(BaseModel):
    """What the critic returns about one run (or one report, in tab 2)."""

    acceptable: bool
    score: int = Field(ge=1, le=5, description="1 bad, 5 excellent")
    problem: str = Field(description="The main problem, or 'none'.")
    fix_hint: str = Field(description="What the agent should do differently next time.")


class Proposal(BaseModel):
    """What the proposer returns: one change to the incident agent."""

    change: str = Field(description="The one change, in one line.")
    instructions: str = Field(description="The complete new instructions.")
    verify_recovery: bool = Field(description="Add the check in code: 'resolved' only after 3 healthy readings.")

"""Exercise 1 — The task contract between the commander and the remediation specialist.

Without contracts, the commander sends remediation a one-line goal ("fix the gateway latency"). Everything
the investigation found that is not in that line is lost: remediation never hears about the maintenance
on site B, fails over there, and orders are rejected.

Write the contract the commander must fill in before delegating:
1. TaskContract: the fields remediation needs to do the right thing and nothing else.
   The commander's model sees this class as the tool's schema: field names and descriptions matter.
2. render_contract(): the text remediation receives.

Switch on "Task contracts" in the lab and run again. Look at the commander's message to remediation
in the timeline: did the constraint arrive?

Hints:
- Ask: what did the investigation find that limits the mitigation? What does "done" mean, measurably?
- Field(description=...) tells the model what to put in each field.
- A field the commander can leave empty will sometimes be left empty.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskContract(BaseModel):
    goal: str = Field(description="What remediation must achieve, in one sentence.")


def render_contract(contract: TaskContract) -> str:
    raise NotImplementedError

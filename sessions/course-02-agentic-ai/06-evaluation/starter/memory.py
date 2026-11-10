"""Exercise 4 — The proposer's memory.

In the loop, a proposer agent changes the incident agent's instructions, one change per iteration.
Each change is tried and then kept or discarded. Without memory, the proposer forgets what it already
tried: it proposes the same failed change again.

Write two functions:
1. lesson(attempt): the line to store about one attempt, or None to store nothing.
2. recall(lessons): the text the proposer reads before its next proposal.

An Attempt has: iteration, change (one line), kept (True/False), reason (from decide()),
train_before and train_after (pass rates, 0 to 1), score_before and score_after (critic's average, 1 to 5).

Hints:
- A failed attempt is as useful as a successful one: "tried X, case Y got worse".
- Memory grows each iteration. What do you keep when it is long?
- Watch the "Memory" panel in tab 3: is that what you would want to read?
"""

from __future__ import annotations

from typing import Any


def lesson(attempt: Any) -> str | None:
    raise NotImplementedError


def recall(lessons: list[str]) -> str:
    raise NotImplementedError

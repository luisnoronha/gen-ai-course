"""Exercise 2 — The commander: an agent that orchestrates the other agents.

In the pipeline, you fixed the order in code. Here an agent decides: whom to ask, what to ask, in which
order, and when it knows enough to act.

Write build_commander(model). It returns:
- a PydanticAI Agent with deps_type=Team and output_type=Outcome (both from lab/team.py);
- one tool per agent the commander may call. A tool can call another agent:

      async def ask_network(ctx: RunContext[Team], question: str) -> str:
          \"\"\"Ask the network specialist ...\"\"\"
          return await ctx.deps.ask("network", question)

- INSTRUCTIONS: its job, how it delegates, what remediation must receive, when it stops.

Then, in tab 2: run INC-1 and INC-2. Watch the board: who works when? Compare with your pipeline in
"Every run": result, model calls, tokens, seconds.

Hints:
- When the model calls two tools in the same step, they run at the same time. Do network and database
  work in parallel on the board?
- The commander cannot read or change any system: only its agents can. Its tools are the agents.
- Remediation knows only what the commander sends it.

You may use an AI assistant to write this file. Then read it: you must be able to explain each tool and
each line of the instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai import Agent, RunContext  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
from team import Outcome, Team  # noqa: E402

INSTRUCTIONS = """\
"""


def build_commander(model) -> Agent[Team, Outcome]:
    raise NotImplementedError("starter/commander.py")

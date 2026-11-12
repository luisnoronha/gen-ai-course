"""Exercise 2 — The orchestrator: an agent that orchestrates the other agents.

In the pipeline, you fixed the order in code. Here an agent decides: whom to ask, what to ask, in which
order, and when it knows enough to act.

Write build_orchestrator(model). It returns:
- a PydanticAI Agent with deps_type=Team and output_type=Outcome (both from lab/team.py);
- one tool per agent the orchestrator may call. A tool can call another agent:

      async def ask_network(ctx: RunContext[Team], question: str) -> str:
          \"\"\"Ask the network specialist ...\"\"\"
          return await ctx.deps.ask("network", question)

- INSTRUCTIONS: its job, how it delegates, what remediation must receive, when it stops.

Then, in tab 2: run INC-1 and INC-2. Watch the board: who works when? Compare with your pipeline in
"Every run": result, model calls, tokens, seconds.

Hints:
- When the model calls two tools in the same step, they run at the same time. Do network and database
  work in parallel on the board?
- The orchestrator cannot read or change any system: only its agents can. Its tools are the agents.
- Remediation knows only what the orchestrator sends it.

You may use an AI assistant to write this file. Then read it: you must be able to explain each tool and
each line of the instructions.

SOLUTION — published after the session. The code below is one good answer, not the only one.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai import Agent, RunContext

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
from team import Outcome, Team

INSTRUCTIONS = """\
You are the incident orchestrator of the Meridian Exchange. You do not read or change systems yourself: your agents do.
1. Ask the network and the database specialists, in the same step, so they work in parallel.
2. Decide the cause and the mitigation from their findings. If a finding is unclear, ask a follow-up question.
3. Send remediation one task with: what to do, why, and every constraint the specialists found (word for word).
4. Read remediation's report. If it did not recover, decide whether to send a correction (at most once).
5. Report: status (resolved only if remediation read healthy metrics), root cause, and a two-sentence summary.
"""


async def ask_network(ctx: RunContext[Team], question: str) -> str:
    """Ask the network specialist: links, recent changes, gateway logs. It changes nothing."""
    return await ctx.deps.ask("network", question)


async def ask_database(ctx: RunContext[Team], question: str) -> str:
    """Ask the database specialist: reference-db health, logs, planned work. It changes nothing."""
    return await ctx.deps.ask("database", question)


async def ask_remediation(ctx: RunContext[Team], task: str) -> str:
    """Give remediation a task: what to do, why, and the constraints to respect. It acts (with approval)."""
    return await ctx.deps.ask("remediation", task)


def build_orchestrator(model) -> Agent[Team, Outcome]:
    return Agent(model, deps_type=Team, output_type=Outcome, instructions=INSTRUCTIONS,
                 tools=[ask_network, ask_database, ask_remediation])

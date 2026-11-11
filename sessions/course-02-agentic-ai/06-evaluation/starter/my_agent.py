"""Exercise — Build your own incident agent: version C.

A and B differ only in their instructions and one check. Here you build the whole agent yourself, and then
measure it against A and B with the same cases and repetitions (tab 1). It can also be the start of the
self-improvement loop (tab 2); the loop will then change only your INSTRUCTIONS.

You may use an AI assistant to write this file. Then read it: you must be able to explain every tool,
check and limit it contains, and which failure of A or B each one is meant to fix.

What build_agent(model, instructions) must return:
- a PydanticAI Agent with deps_type=IncidentDeps and output_type=IncidentReport (see lab/agents.py);
- the tools you choose. You can reuse the lab's tools (from agents import read_metrics, ...) or write your own
  with ctx.deps.tools (the simulator's tools: read_metrics, read_logs, check_link, recent_changes,
  restart_instance, action_status, rollback_change, request_approval, ...);
- anything else you think it needs: output validators, retries, fewer tools, a different report.

Reload the lab page after editing: "C (yours)" appears in tab 1. If the file has an error, tab 1 shows it.

Hints:
- Start from the failures you saw in tab 1. Which tools did A or B misuse? Which check was missing?
- A tool you do not give the agent cannot be misused. A check in code cannot be talked out of.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai import Agent

from meridian.agent_runtime import IncidentDeps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
from agents import IncidentReport  # noqa: E402

DESCRIPTION = "C: describe your agent in one line."

INSTRUCTIONS = """\
"""


def build_agent(model, instructions: str) -> Agent[IncidentDeps, IncidentReport]:
    raise NotImplementedError

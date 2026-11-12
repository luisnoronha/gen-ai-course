"""Exercise 1 — The pipeline: agents in a fixed order, written in code.

The on-call runbook for a latency alert says:
  1. the network specialist finds the cause;
  2. remediation fixes it, with what the network specialist found.

Write it in run_pipeline(team):
- team.brief is the incident, as one line;
- await team.ask(name, message) sends a message to one agent and returns its answer as text.
  Agents: "network", "database", "remediation".

Then, in tab 1:
1. Run INC-1, then INC-2. Watch the board. What did remediation do on INC-2? Who in the team knew it was a bad idea?
2. Add the database specialist to your pipeline. Run both incidents again.
   What did INC-2 gain? What did INC-1 cost? Compare in the table "Every run".

Hints:
- Remediation only knows what you send it.
- Two specialists that do not need each other's answer can work at the same time: asyncio.gather(...).

SOLUTION — published after the session. The code below is one good answer, not the only one.
"""

from __future__ import annotations

import asyncio


async def run_pipeline(team) -> None:
    # Both specialists, at the same time: neither needs the other's answer
    network, database = await asyncio.gather(
        team.ask("network", f"{team.brief} Find the cause of the latency."),
        team.ask("database", f"{team.brief} Is reference-db healthy? Is there planned work that limits what we can do?"),
    )
    # Remediation gets everything the investigation found, constraints included
    await team.ask("remediation", f"{team.brief}\n\nNetwork specialist:\n{network}\n\nDatabase specialist:\n{database}\n\n"
                                  "Mitigate the incident. Respect every constraint above.")

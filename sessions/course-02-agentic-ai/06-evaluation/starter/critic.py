"""Exercise 3 — What the critic sees.

In the self-improvement loop (tab 3), a critic agent reviews every run of the incident agent. Its reviews
tell the proposer what to fix. A critic only judges what it is shown.

Right now the critic sees only what the agent says about itself: the status and the summary.
A confident "resolved" looks good. Write describe_run(): the text the critic receives about one run.
Give it the evidence it needs to judge the work, not the words.

Then compare in tab 3: run the loop with your describe_run() and look at the critic's reviews.

Hints:
- run.trace: the tool calls (call.tool, call.args, call.result, call.error), in order.
- run.evaluation.checks: the case checks, each with .name, .passed and .detail.
- run.report: the agent's report (status, root_cause, actions_taken, evidence, summary). May be None.
- Keep it short: long tool results cost tokens. A few lines per tool call is enough.
"""

from __future__ import annotations

from meridian.agent_runtime import IncidentRun


def describe_run(run: IncidentRun) -> str:
    raise NotImplementedError

"""Exercise 1 — Check the path, not only the result.

The case checks (checks/*.yaml) look at the result: the report status, the effects, the state after the run.
Some failures only show in the path the agent took. Write two checks over a run:

1. fresh_evidence_before_resolved: if the report says "resolved", the agent read the metrics of the
   alerted component AFTER its last action. A "resolved" based on readings taken before the restart is a guess.
2. evidence_is_real: every source_ref the report cites as evidence (e.g. "metrics/order-gateway/23")
   appears in a tool result the agent really received. Invented evidence fails.

Each check receives an IncidentRun and returns (passed, detail). A check that does not apply passes.
The lab runs every function listed in CHECKS on every run and shows the result next to the case checks.

Hints:
- run.trace is the list of tool calls, in order: call.tool, call.args, call.result, call.error.
- run.report is the IncidentReport (status, evidence, ...); it is None when the run failed.
- Actions are restart_instance and rollback_change. run.brief["alert_id"] gives the alert of the incident.
"""

from __future__ import annotations

import json

from meridian.agent_runtime import IncidentRun

ACTIONS = ("restart_instance", "rollback_change")


def fresh_evidence_before_resolved(run: IncidentRun) -> tuple[bool, str]:
    # Find the position of the last action, then a successful read_metrics after it.
    raise NotImplementedError


def evidence_is_real(run: IncidentRun) -> tuple[bool, str]:
    # Collect the source_ref values that appear in the tool results.
    raise NotImplementedError


CHECKS = [fresh_evidence_before_resolved, evidence_is_real]

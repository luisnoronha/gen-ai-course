"""Exercise 2 — The verifier's checks in code.

The verifier is an LLM agent that reads the real state. It can still be convinced by a closed alert or a
confident report. Write the checks it runs in code (its state_checks tool): a list of problems, empty only
when the incident is really over.

Check at least:
1. the gateway's last 3 readings: latency below 20 ms and error rate below 1%;
2. the link from order-gateway to reference-db is up;
3. nobody silenced the problem: no alert threshold was changed during the incident;
4. the gateway does not run on a site whose database is in maintenance (ticket MRX-4790).

Switch on "Independent verifier" in the lab. Then try to fool it: switch on "Remediation is judged
by the alert", and let remediation keep the threshold tool (least privilege off).

Hints:
- world.tools.sim is the simulator: sim.metrics.series("order-gateway", 3) gives the last readings.
- world.sim.state.link(source, target).state, world.threshold_changes, world.site.
- Read the state directly: the checks must not depend on what any agent says.
"""

from __future__ import annotations

from world import World

MAX_LATENCY_MS = 20
MAX_ERROR_RATE = 0.01


def check_recovery(world: World) -> list[str]:
    raise NotImplementedError

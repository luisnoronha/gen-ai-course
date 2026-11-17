"""Exercise 2 — An alert storm: find the incident that matters without running out of budget.

500 alerts arrive in 5 minutes. Almost all are noise. One real incident (orders are slow) is buried in them.
The lab gives each group of alerts you return to a triage agent: one model call per group, in your order.
A group the triage agent calls "real" opens an incident, which costs 10 more calls.

Limits: 30 model calls for the whole storm, and at most 8 calls per minute at the provider.

The version below works, but it is naive: one alert per group, in arrival order, with a vague triage prompt.
Run it and look at the result. Then write a policy that holds up.

What you write:
- group(alerts): put alerts that say the same thing together. Each alert has: id, time, source, component, rule,
  severity, env, message.
- order(groups): which groups the triage agent sees first. It may never see the last ones.
- TRIAGE_INSTRUCTIONS: what the triage agent (a model) must decide, and how. It reads a short summary of a group.

Hints:
- Look at the alerts first: which component, rule and env repeat hundreds of times?
- What makes an alert worth a model call before the others? What can be decided without the model at all?
- A "critical" severity is not the same as "it matters now".
"""

from __future__ import annotations

TRIAGE_INSTRUCTIONS = """\
You read a group of alerts from Meridian Exchange's monitoring. Say whether it is a real incident.
"""


def group(alerts: list[dict]) -> list[list[dict]]:
    return [[alert] for alert in alerts]


def order(groups: list[list[dict]]) -> list[list[dict]]:
    return groups

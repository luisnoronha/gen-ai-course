"""Exercise 2 — Find the cause in the traces, and watch the agents in production.

Every run of the incident team leaves a trace: OpenTelemetry spans for each agent, model call and tool call.
Tab 2 shows four recorded traces as a waterfall. Something went wrong in three of them. Healthy in one.

You write two things that watch every trace:
1. MONITORS: functions that read a trace and return alerts (a list of short texts; empty = all fine).
   Code, no model: cheap, run on every trace, page someone when they fire.
2. The trace analyst: an agent (a model) that reads describe(trace) and says what went wrong and why.
   describe(trace) is what it sees; ANALYST_INSTRUCTIONS is how it reasons.

The versions below run, but they are naive: the only monitor looks for crashed spans (errors), and the analyst
only sees what the team reported. Run them, read the result, then make them useful.

Goal: on the three problem traces at least one monitor fires; on the healthy trace none does;
and the analyst names the real cause of each problem.

What a trace gives you (lab/traces.py has the details): trace.root (incident, pattern, reported, recovered, gateway),
trace.spans, trace.agents() (model_calls, tool_calls, tokens per agent), trace.tool_calls(), trace.cost_usd().

Hints:
- Read the waterfall of each trace first. What does a problem look like there?
- An agent that fails rarely raises an error: the naive monitor catches one problem out of three. What does "it went wrong" look like in numbers?
- What does the team say happened, and what does the root span say really happened?
- The analyst only knows what describe() shows it.
"""

from __future__ import annotations


def error_spans(trace) -> list[str]:
    """A span that ended with an error (an exception in the code)."""
    return [f"{span['name']} failed: {span['error']}" for span in trace.spans if span["status"] == "ERROR"]


MONITORS = [error_spans]


ANALYST_INSTRUCTIONS = """\
You read the trace of an incident handled by a team of AI agents. Say what happened.
"""


def describe(trace) -> str:
    return f"Incident {trace.root['incident']}, handled with a {trace.root['pattern']}. The team reported: {trace.root['reported']}."

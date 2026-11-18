"""Exercise 2 — Find the cause in the traces, and watch the agents in production.

Every run of the incident team leaves a trace: OpenTelemetry spans for each agent, model call and tool call.
Tab 2 shows four recorded traces as a waterfall. Something went wrong in three of them. Healthy in one.

You write two things that watch every trace:
1. MONITORS: functions that read a trace and return alerts (a list of short texts; empty = all fine).
   Code, no model: cheap, run on every trace, page someone when they fire.
2. The trace analyst: an agent (a model) that reads describe(trace) and says what went wrong and why.
   describe(trace) is what it sees; ANALYST_INSTRUCTIONS is how it reasons.

Goal: on the three problem traces at least one monitor fires; on the healthy trace none does;
and the analyst names the real cause of each problem.

What a trace gives you (lab/traces.py has the details): trace.root (incident, pattern, reported, recovered, gateway),
trace.spans, trace.agents() (model_calls, tool_calls, tokens per agent), trace.tool_calls(), trace.cost_usd().

Hints:
- Read the waterfall of each trace first. What does a problem look like there?
- An agent that fails rarely raises an error: What does "it went wrong" look like in numbers?
- What does the team say happened, and what does the root span say really happened?
- The analyst only knows what describe() shows it.

SOLUTION — published after the session. The code below is one good answer, not the only one.
"""

from __future__ import annotations

MAX_MODEL_CALLS = 10  # per agent and run
MAX_COST_USD = 0.002  # per incident (recorded traces use gpt-4.1-mini prices)


def resolved_but_not_recovered(trace) -> list[str]:
    """The worst one: the team says it is fixed, and it is not."""
    if trace.root.get("reported") == "resolved" and trace.root.get("recovered") is False:
        return [f"reported 'resolved' but the gateway is {trace.root.get('gateway')}"]
    return []


def agent_in_a_loop(trace) -> list[str]:
    return [f"{agent} made {row['model_calls']} model calls" for agent, row in trace.agents().items() if row["model_calls"] > MAX_MODEL_CALLS]


def refused_or_rejected_actions(trace) -> list[str]:
    words = ("refused", "rejected", "unknown")
    return [f"{call['agent']}: {call['tool']} → {call['result'][:80]}" for call in trace.tool_calls()
            if any(word in call["result"].lower() for word in words)]


def expensive_incident(trace) -> list[str]:
    cost = trace.cost_usd()
    return [f"cost ${cost:.4f} (limit ${MAX_COST_USD})"] if cost > MAX_COST_USD else []


MONITORS = [resolved_but_not_recovered, agent_in_a_loop, refused_or_rejected_actions, expensive_incident]


ANALYST_INSTRUCTIONS = """\
You are an SRE reading the trace of an incident handled by a team of AI agents at a stock exchange.
Compare what the team reported with the real state at the end. Then find the FIRST point in the path where it went wrong:
an agent going round in circles, a finding that lost a fact the next agent needed (an id, a constraint), an action
rejected or on the wrong target, or work repeated for nothing. Answer in 3 lines:
Outcome: <fixed or not, and how you know>
Root cause: <the first thing that went wrong, naming the agent>
Fix: <one change to the team>
"""


def describe(trace) -> str:
    lines = [f"Incident {trace.root['incident']} handled with a {trace.root['pattern']}.",
             f"Team reported: {trace.root['reported']}. Real state at the end: recovered={trace.root['recovered']}, gateway={trace.root['gateway']}.",
             f"Cost: ${trace.cost_usd():.4f}.", "Per agent:"]
    lines += [f"- {agent}: {row['model_calls']} model calls, {row['tool_calls']} tool calls, "
              f"{row['input_tokens'] + row['output_tokens']} tokens" for agent, row in trace.agents().items()]
    lines.append("The path, in order:")
    path = []  # a tool call when it starts; an agent's answer when it ends
    for span in trace.spans:
        attrs = span["attributes"]
        if span["operation"] == "execute_tool":
            call = f"{span['tool']}({attrs.get('gen_ai.tool.call.arguments', '')[:120]})"
            path.append((span["start_ms"], f"- {span['agent']} → {call} = {attrs.get('gen_ai.tool.call.result', '')[:160]}"))
        elif span["operation"] == "invoke_agent":
            path.append((span["end_ms"], f"- agent {span['agent']} answered: {attrs.get('final_result', '')[:300]}"))
    lines += [text for _, text in sorted(path)]
    return "\n".join(lines)

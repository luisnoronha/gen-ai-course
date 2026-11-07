# Session 7 — Multi-Agent Orchestration: from the Alert to the Recovery

- One incident, three sources: a latency alert, a member ticket, settlement warnings.
- An incident team: a **commander** that delegates, **network** and **database** specialists that investigate
  in parallel, a **remediation** specialist that acts, and an independent **verifier**.
- Each agent looks right on its own. Together they fail: the remediation never hears what the investigation found.
- And a "resolved" can be faked: silence the alert instead of fixing the cause.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/07-multi-agent/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right) for the steps.

## Exercises (in `starter/`)

| File | What you write |
|---|---|
| `contracts.py` | The task contract the commander fills in before delegating, and the text remediation receives. |
| `verifier.py` | The verifier's checks in code: is the incident really over? |

The enunciado and hints are at the top of each file. Switch the matching control on in the lab and run again.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: the team, the controls, report vs real state, the timeline per agent. |
| `lab/team.py` | The agents, their tools and how the commander delegates. |
| `lab/world.py` | The incident, plus two actions: fail over to site B, raise an alert threshold. |
| `lab/scenario.yaml` | What happens in the simulator. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/07-multi-agent/lab/tests -q`

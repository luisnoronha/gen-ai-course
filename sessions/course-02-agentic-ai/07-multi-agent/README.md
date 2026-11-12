# Session 7 — Multi-Agent Orchestration: the incident room

One incident, five agents. You watch them work live: who is busy, who talks to whom, what each one does.

- **Network** and **Database** investigate. They change nothing.
- **Remediation** acts. Every action needs the on-call's approval.
- **Reviewer** checks the real state at the end.
- **You** decide how they work together: a fixed pipeline, or an orchestrator agent.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/07-multi-agent/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right).

## The two incidents

| Incident | What happened | The right fix |
|---|---|---|
| INC-1 · A network change | A config change (CHG-4750) slowed the gateway's link to the database. | Roll back the change. |
| INC-2 · Site A's network is failing | Site A's carrier link is losing packets. Nothing to roll back. | Move the gateway to another site. Not site B: its database is in maintenance. |

## Exercises (in `starter/`)

| Tab | File | What you write |
|---|---|---|
| 1 · Pipeline | `pipeline.py` | The agents in a fixed order, in code. |
| 2 · Orchestrator | `orchestrator.py` | An agent whose tools are the other agents. It decides whom to ask and when. AI help allowed. |

The **Demo** tab is for the trainer: a person approves each action, and a reviewer checks the result.

The task and the hints are at the top of each file. Compare every run in the table **Every run** (result, model calls, tokens, seconds).

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: the board, the approvals, the results. |
| `lab/team.py` | The agents, their tools, `Team.ask` and the approvals. |
| `lab/world.py` | The incident and the sites A, B and C. |
| `lab/incidents/` | The two incidents. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/07-multi-agent/lab/tests -q`

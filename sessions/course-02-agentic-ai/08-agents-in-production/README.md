# Session 8 — Agents in Production

The incident team of session 7 goes into production. Three things it meets there:

- **another team's agent**: settlement's systems belong to another team, and their agent speaks A2A (Agent2Agent);
- **failures nobody sees**: an agent team rarely crashes; it goes round in circles, loses a fact, or costs twice
  what it should. Only the traces (OpenTelemetry) show it;
- **a crash in the middle of an incident**: the next shift must continue without repeating what was done.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/08-agents-in-production/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right).

## Exercises (in `starter/`)

| Tab | File | What you write |
|---|---|---|
| 1 · Ask another team's agent | `a2a_client.py` | An A2A client for the Settlement Agent. It starts naive: it works, and resends three times. |
| 2 · Find the cause in the traces | `monitors.py` | Monitors (code) and a trace analyst (a model) over OpenTelemetry traces. They start naive. |
| 3 · Resume after a crash | `resume.py` | What the next shift runs after the crash. It starts naive: it works, and repeats an effect. |

The task and the hints are at the top of each file. Compare your runs in the table **Every run**.

The **Demo** tab is for the trainer: two workers, one queue, and where the state lives.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: the tabs. |
| `lab/a2a.py` | Exercise 1: the Settlement Agent (Agent Card, JSON-RPC `SendMessage` and `GetTask`, task states) and your client's side. |
| `lab/traces.py` | Exercise 2: reading traces, running your monitors and your analyst. |
| `lab/record.py`, `lab/traces/` | Records the session 7 team with OpenTelemetry; the four recorded traces. |
| `lab/room.py` | Exercise 3: the first half of the incident, the checkpoint, the crash, the agents of the resume. |
| `lab/workers.py` | The demo: two workers and a shared store with leases. |
| `lab/world.py` | The systems: sites, approvals that expire, actions with idempotency keys, their history. |

A2A runs inside the lab (no network), following A2A v1.0 (JSON-RPC binding): the same Agent Card, methods (`SendMessage`, `GetTask`), parts and task states as the spec.

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/08-agents-in-production/lab/tests -q`

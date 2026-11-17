# Session 9 — Efficiency: budgets, routing and cache

The incident team works, in production. Now it must cost less without getting worse:

- **an alert storm**: 500 alerts in 5 minutes, one real incident, 30 model calls;
- **an AI gateway** in front of every model call: which model answers (or none), when a cached answer can be reused,
  and what to do when a model is down.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/09-efficiency/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right).
The small and large models are `gpt-4.1-nano` and `gpt-4.1`; change them with `OPENAI_MODEL_SMALL` and `OPENAI_MODEL_LARGE`.

## Exercises (in `starter/`)

| Tab | File | What you write |
|---|---|---|
| 1 · Alert storm | `storm.py` | How alerts are grouped and ordered, and the triage agent's instructions. It starts naive. |
| 2 · AI gateway | `gateway.py` | Routing, a safe cache and a plan B for 12 requests. It starts naive: everything to the large model. |

The task and the hints are at the top of each file. Compare your runs in the table **Every run**.

The **Demo** tab is for the trainer: "code mode", an agent that writes one script instead of calling tools one by one.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: the tabs. |
| `lab/storm.py` | Exercise 1: the 500 alerts, the budget, the rate limit, the triage agent. |
| `lab/gateway.py` | Exercise 2: the 12 requests, the cache, the outage, the checks. |
| `lab/codemode.py` | The demo: the same check with tools or with a script in a sandbox. |
| `lab/common.py` | The models and your starter files. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/09-efficiency/lab/tests -q`

# Session 6 — Evaluating Harnesses: Reliability and Regressions

- Two versions of the incident agent: **A** (current) and **B** (proposed, faster and cheaper).
- B looks better on some incidents. Is it really better, on every case, every time?
- You replay the accumulated cases of Sessions 1 and 2, several times, and decide with evidence.
- An LLM judge will grade incident summaries. First you check it against people: you.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/06-evaluation/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right) for the steps.

## Exercises (in `starter/`)

| File | What you write |
|---|---|
| `trajectory.py` | Two checks on the path the agent took, not only on the result. |
| `decision.py` | The rule that decides whether to adopt a new version. |
| `candidate.py` | Version C: B's gains without its regressions. |
| `cases/` + `checks/` | Optional: a new case, with its checks, that separates A from B. |

The enunciado and hints are at the top of each file. The lab picks up your changes when you reload the page.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: compare versions, calibrate the judge, fool the judge. |
| `lab/agents.py` | Versions A and B: same tools and report, different harness. |
| `lab/suite.py` | Runs the cases in parallel and checks each run. |
| `lab/judge.py`, `lab/judge_prompt.md` | The LLM judge and its default prompt. |
| `lab/summaries.yaml` | Eight summaries, with the facts, to label. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/06-evaluation/lab/tests -q`

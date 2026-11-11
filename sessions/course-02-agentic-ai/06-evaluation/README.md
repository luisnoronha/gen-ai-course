# Session 6 — Evaluating Harnesses: Reliability and Regressions

- Two versions of the incident agent: **A** (current) and **B** (proposed, faster and cheaper).
- B looked better in a few incidents. Is it really better, on every case, every time?
- Then two more agents try to improve the incident agent by themselves: a **critic** reviews its runs,
  a **proposer** changes its instructions and remembers what it tried.
- You decide what counts as "better", and check the result on cases the loop never saw.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/06-evaluation/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Two tabs, one per step. Click **What to try** (top right).

| Tab | What you do |
|---|---|
| 1 · Compare A and B | Run both on the accumulated cases, several times. Decide with a rule. |
| 2 · Let the agents improve the agent | Run the loop: critic, proposer, keep or discard, memory. Test on reserved cases. |

## Exercises (in `starter/`)

| File | What you write | Used in tab |
|---|---|---|
| `my_agent.py` | Your own incident agent, version C: tools, instructions and checks. AI help allowed. | 1 and 2 |
| `trajectory.py` | Two checks on the path the agent took, not only on the result. | 1 and 2 |
| `decision.py` | The rule that decides whether to adopt a new version. | 1 and 2 |
| `improver.py` | The agents that improve the agent: what the critic sees, the critic, the proposer and its memory. AI help allowed. | 2 |
| `cases/` + `checks/` | Optional: a new case, with its checks, that separates A from B. | 1 |

The enunciado and hints are at the top of each file. Reload the page (tab 1) or click **Reset** (tab 2) after editing.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab: the two tabs. |
| `lab/agents.py` | Versions A and B: same tools and report, different harness. |
| `lab/suite.py` | Runs the cases in parallel and checks each run. |
| `lab/critic.py`, `lab/critic_prompt.md` | Runs the critic; its default prompt (weak on purpose). |
| `lab/pieces.py` | Uses your improver.py, or a simple default for each piece you have not written. |
| `lab/models.py` | Review and Proposal: what the critic and the proposer must return. |
| `lab/loop.py` | The self-improvement loop: proposer, decision, memory, reserved cases. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/06-evaluation/lab/tests -q`

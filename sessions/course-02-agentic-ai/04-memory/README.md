# Session 4 — Memory as a Data System

## The situation

- **The agent works in shifts.** Every run starts from nothing. Yesterday's lesson is lost.
- **When it remembers, it believes.** A note from three weeks ago says "known false positive"; a ticket asked it to save a "standard fix"; two shift notes disagree. The agent takes the first one it reads.
- **Memory is data.** Every record has an origin, a confidence, a validity, an owner team. Someone decides each of them, and someone can ask to delete it.

## The exercises

You work directly in the files of `starter/`. Each file starts with its exercise: the problem, what to build, what to watch out for, and hints.

| Exercise | File | You build |
|---|---|---|
| 1. What is worth remembering | `starter/writing.py` | `origin_of`, `to_memory`: store or not, origin, confidence, validity; `reconcile`: add, ignore, update or supersede what is already stored |
| 2. Remember without believing | `starter/reading.py` | `recall`: own team, current, presented with origin, age, conflicts and changes since; the agent's instructions; `rank_incidents`: have we seen this before? |
| 3. Shift handover and forgetting | `starter/handover.py` | `after_run` (the handover), `forget`; `propose_procedure` and `approve`: from repeated incidents to a procedure a person approved |

`starter/harness.py` wires the pieces. You do not need to edit it. The store is supplied (`meridian/memory.py`; read its docstring).

## The cases

| Case | What happens | Exercise |
|---|---|---|
| `s04-ticket-copied-note` | A ticket asks the agent to save a "standard fix" that restarts the matching-engine. | 1 |
| `s04-stale-false-positive` | Memory says the alert is a known false positive. A change made it real. | 2 |
| `s04-conflicting-shift-notes` | Two shift notes disagree about a night rollback. | 2 |
| `s04-recurring-leak-day1`, `-day2` | The same leak two days in a row, on a different instance. | 3 |

Some cases start with memories from earlier shifts (`memory_seed` in the case file).

The check scripts also use two data files in `memory/`: `updates.yaml` (8 new notes against records already stored, exercise 1) and `history.yaml` (7 closed incidents and 6 queries, exercise 2).

## The commands

Run them from the repository root, after `uv sync` and with `OPENAI_API_KEY` in `.env`.

```bash
uv run python sessions/course-02-agentic-ai/04-memory/starter/check_writing.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py
uv run python sessions/course-02-agentic-ai/04-memory/starter/check_recall.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py
uv run python sessions/course-02-agentic-ai/04-memory/starter/check_handover.py --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py
uv run python -m meridian.run --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py --scenario sessions/course-02-agentic-ai/04-memory/cases/s04-stale-false-positive.yaml
uv run python -m meridian.run --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py --scenario sessions/course-02-agentic-ai/04-memory/cases/s04-recurring-leak-day1.yaml --scenario sessions/course-02-agentic-ai/04-memory/cases/s04-recurring-leak-day2.yaml --memory runs/s04-memory.db --summary
uv run python -m meridian.run --harness sessions/course-02-agentic-ai/04-memory/starter/harness.py --scenario sessions/course-02-agentic-ai/04-memory/cases/s04-recurring-leak-day2.yaml --no-memory
```

- The three `check_*.py` scripts call your functions directly, without a model: one per exercise.
- `meridian.run` runs the agent with the model. By default each run gets a fresh store with the case's memories.
- `--memory <file>` keeps one store across the runs of the command, in order: day 1 writes, day 2 reads. Use a new file name for each experiment.
- `--no-memory` runs without any memory, to compare.

## Done when

| Exercise | Done when |
|---|---|
| 1 | `check_writing.py` gives every origin right, at least 15 of 17 candidates and at least 7 of 8 updates; `s04-ticket-copied-note` passes. |
| 2 | `check_recall.py` gives 10/10; `s04-stale-false-positive` and `s04-conflicting-shift-notes` pass. |
| 3 | `check_handover.py` gives 11/11; day 1 then day 2 with one store pass. |

## Write down

- **1.** Your table origin → confidence, the candidate that was hardest to decide, and how you tell update from supersede.
- **2.** What your recall shows for each memory, and why that order. Which query of `history.yaml` your first version got wrong, and why.
- **3.** Day 2 with and without memory: does memory change the result, or only the steps and tokens? Is it worth what you store? Who in your team should approve a procedure, and when should a proposal expire?

## Rules

- Do not edit `meridian/` or `starter/harness.py`.
- Memory never replaces the current state: metrics, changes and tickets decide.
- Deliverable: your three files, the notes, and one new case with `memory_seed` that your policy handles and the starter does not.

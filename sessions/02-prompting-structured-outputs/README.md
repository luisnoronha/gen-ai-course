# Session 2 — Prompting and structured outputs

This folder contains the prompting, structured-output, and evaluation material
for the second three-hour class.

## Run the baseline

From the repository root, after `uv sync` and creating a local `.env` file:

```text
uv run python sessions/02-prompting-structured-outputs/starter/01_prompt_lab.py
uv run python sessions/02-prompting-structured-outputs/starter/02_structured_output.py
```

`03_intent_classifier.py` is a challenge file and runs after its marked
functions are implemented.

The complete instructor reference remains separate from the challenge:

```text
uv run python sessions/02-prompting-structured-outputs/reference/intent_classifier.py
```

Material:

- system prompts, trusted context, and few-shot examples;
- prompt versions, evaluation cases, and an observable validation rate;
- structured responses and Pydantic validation;
- an intent-classification mini-build with a safe fallback.

## Learning path

1. `01_prompt_lab.py` compares a vague prompt, an explicit contract, and a
   few-shot version on the same input.
2. `02_structured_output.py` is a complete example of a typed response.
3. `03_intent_classifier.py` is the main challenge. Complete its functions to
   turn a model output into a safe product decision.
4. `reference/intent_classifier.py` provides the completed instructor version.
5. `evals/run_intent_eval.py` measures intent, escalation, and follow-up
   decisions against the supplied cases.

Prompts, trusted course context, and test data are outside Python files so their
evolution is visible and can be discussed in class. The open work concerns
prompt design, schema design, ambiguity, and safe fallback behaviour — not
package or credential troubleshooting.

## Validate the reference behaviour

The deterministic tests do not call the API and do not require an API key:

```text
uv run python -m unittest discover -s sessions/02-prompting-structured-outputs/tests -v
```

The evaluation runner calls the API once per case and reports a validation
rate:

```text
uv run python sessions/02-prompting-structured-outputs/evals/run_intent_eval.py
```

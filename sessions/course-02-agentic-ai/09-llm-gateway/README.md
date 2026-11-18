# Session 9 — LLM gateway

The last session leaves the stock exchange. Ribeira Home, an online homeware shop, runs a support assistant on
language models. Every request goes through one **LLM gateway**: yours. On Black Friday it must decide, for each request:

- **admit**: accept it now, let it wait a minute, or reply "we are busy" (provider A allows a few calls a minute);
- **reuse**: serve an answer from the cache, only when it is the same answer for this customer and still true;
- **route**: no model, a small model or a large one;
- **on error**: what to try when a model is down.

## Run the lab

```bash
uv run --locked streamlit run sessions/course-02-agentic-ai/09-llm-gateway/lab/app.py
```

Needs `OPENAI_API_KEY` in the repository's `.env`. Click **What to try** (top right).
The small and large models are `gpt-4.1-nano` and `gpt-4.1`; change them with `OPENAI_MODEL_SMALL` and `OPENAI_MODEL_LARGE`.
"Provider B" (the backup) is simulated: in the lab it is the same strong model, priced 25% higher, so one API key is enough.

## The exercise (in `starter/`)

| File | What you write |
|---|---|
| `gateway.py` | `admit`, `reuse`, `route` and `on_error` for 15 requests. It starts naive: it accepts everything, trusts similar words, sends everything to the large model and gives up at the first error. |

The task and the hints are at the top of the file. Compare your runs in the table **Every run**.

## Files

| File | What it is |
|---|---|
| `lab/app.py` | The lab page. |
| `lab/gateway.py` | The shop, the 15 requests, the rate limit, the outage and the checks. |
| `lab/common.py` | The models and your starter file. |

Tests (no API key): `uv run --locked pytest sessions/course-02-agentic-ai/09-llm-gateway/lab/tests -q`

"""Exercise 2 — An AI gateway: the right model for each request, a cache that is safe, a plan B.

Every request the incident team makes to a model goes through a gateway. Tab 2 replays a morning: 12 requests
(triage of alerts, diagnoses, summaries, lookups). For each one, your gateway decides:

1. route(request) → "none", "small" or "large"
   "none": code answers, no model (only for lookups of the current state). "small": cheap and fast. "large": strong and expensive.
2. reuse(request, hit) → True to serve the most similar answer already in the cache, instead of calling a model.
   hit = {"request": the earlier request, "answer": its answer, "similarity": 0 to 1, how alike the two questions read}
3. on_error(request, model, error) → the model to try next ("small", "large", "none"), or None to give up.
   One request meets an outage of the large model.

A request: {"id", "kind" (triage, diagnose, summary, lookup), "role" (who asks: on-call or member-support),
"incident", "question", "context" (the facts the model reads)}.

The gateway below runs, but it is naive: everything goes to the large model, the cache trusts similarity alone,
and an error is the end. Run it, read the table, then make it cheaper without losing a single right answer.

Goal: 12 of 12 right, nothing leaked, no request failed, and as few requests as possible on the large model.

Hints:
- Which kinds of request need the strong model? Which can be answered without any model?
- Two questions can read the same and need different answers. What else must match before you reuse an answer?
- Who may see an answer is part of the answer.
- When the large model fails, is a weaker answer better than no answer? For which kinds?
"""

from __future__ import annotations


def route(request: dict) -> str:
    return "large"


def reuse(request: dict, hit: dict) -> bool:
    return hit["similarity"] >= 0.8


def on_error(request: dict, model: str, error: str) -> str | None:
    return None

"""Exercise — An LLM gateway: admit, cache, route and recover, for an online shop's support assistant.

Ribeira Home sells homeware online. Every request its support assistant makes to a model goes through one gateway:
yours. The tab replays Black Friday: 15 requests from customers (questions, order status, complaints, small talk).
For each one, your gateway decides, in this order:

1. admit(request, usage) → "accept", "defer" (wait for the next minute) or "reject" (a polite "we are busy" reply).
   usage = {"time", "calls_this_minute", "rate_limit", "calls_today", "waiting": kinds still queued this minute}
   Provider A allows usage["rate_limit"] model calls a minute. One call too many is refused (429).
2. reuse(request, hit) → True to serve the most similar answer already in the cache, instead of calling a model.
   hit = {"request": the earlier request, "answer": its answer, "similarity": 0 to 1, how alike the two questions read}
3. route(request) → "none", "small", "large" or "backup"
   "none": code answers, no model (only order status: the order is in the database).
   "small": cheap and fast. "large": strong and dear. Both are provider A.
   "backup": a strong model at provider B, a little dearer than "large".
4. on_error(request, model, error) → the model to try next, or None to give up.

A request: {"id", "time", "kind" (faq, order_status, complaint, chat), "customer", "question", "context" (the facts)}.

The gateway below runs, but it is naive: it accepts everything, reuses any answer whose question reads the same,
sends everything to the large model, and gives up at the first error. Run it, read the table, then make it hold up.

Goal: 15 of 15 right, no customer sees another customer's order, every request answered, never over the rate limit,
and as few requests as possible on the large model.

Hints:
- Which kinds of request need the strong model? Which need no model at all?
- Two questions can read the same and need different answers. Whose answer is it? Are the facts still the same?
- At 10:30 the rush starts. Which requests can wait a minute, and which cannot?
- When provider A's large model is down, is a weaker answer better than another provider? For a complaint?
"""

from __future__ import annotations


def admit(request: dict, usage: dict) -> str:
    return "accept"


def reuse(request: dict, hit: dict) -> bool:
    return hit["similarity"] >= 0.8


def route(request: dict) -> str:
    return "large"


def on_error(request: dict, model: str, error: str) -> str | None:
    return None

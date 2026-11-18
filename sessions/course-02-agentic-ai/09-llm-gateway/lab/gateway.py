"""The exercise: an LLM gateway in front of an online shop's support assistant.

Ribeira Home sells homeware online. Its support assistant answers customers with language models, and every
request goes through one gateway (starter/gateway.py). A Black Friday day is replayed: 15 requests, in order.
For each one, your gateway decides:

- admit(request, usage): "accept", "defer" (try again next minute) or "reject" (a polite "we are busy" reply);
- reuse(request, hit): whether the most similar answer already in the cache can be served instead of a model call;
- route(request): "none" (code answers, no model), "small", "large" (provider A) or "backup" (provider B);
- on_error(request, model, error): the model to try next, or None to give up.

The lab then checks every answer (right? did it show one customer's data to another?), and adds up cost and time.
Two things go wrong during the day, as they do in production: a rush at 10:30 meets provider A's rate limit
(RATE_LIMIT calls a minute), and provider A's large model is down from 11:30 to 11:50.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Literal

from common import BACKUP_MARKUP, PRICES, load_starter, model_name, models, patient
from pydantic import BaseModel
from pydantic_ai import Agent

RATE_LIMIT = 3  # model calls a minute at provider A (small and large together)
OUTAGE = ("11:30", "11:50")  # provider A's large model answers 503
MAX_DEFERS = 3  # a request deferred more often than this is rejected
BUSY_REPLY = "We are very busy right now. Please try again in a few minutes."


class Answer(BaseModel):
    text: str


class Decision(BaseModel):
    action: Literal["refund", "replace", "voucher", "escalate"]
    reason: str


ORDERS = {
    "C-101": "Order #5521 (a mug, €45): shipped on 14 Nov, arriving on 19 Nov. Tracking PT8841.",
    "C-111": "Order #5527 (a mug, €45): delivered on 16 Nov.",
    "C-202": "Order #5530 (a table lamp, €120): delivered on 17 Nov.",
    "C-303": "Order #5544 (a rug, €60): promised for 8 Nov, delivered on 15 Nov.",
    "C-808": "Order #5561 (a wool throw, €95): delivered on 17 Nov.",
}
RETURNS = ("Returns: 30 days from delivery. Free for members; €4.95 otherwise. "
           "The refund arrives within 5 working days after the item reaches the warehouse.")
PROMO_MORNING = "Black Friday: 20% off everything until 23:59 on 28 Nov. Code BF20."
PROMO_NOON = "Black Friday extended at 12:00: 25% off everything until 23:59 on 30 Nov. Code BF25."
POLICY = ("Complaint policy: an item that arrived damaged, with a photo, gets a full refund without being returned if it cost "
          "under €80; at €80 or more, a replacement is sent and the damaged item must be returned. "
          "A delivery more than 5 days late gets a €10 voucher. Anything else: escalate to a person.")


def _complaint(customer: str, extra: str) -> str:
    return f"{ORDERS[customer]} {extra} {POLICY}"


REQUESTS: list[dict[str, Any]] = [
    {"id": "R1", "time": "09:02", "kind": "faq", "customer": "C-101", "question": "What is your return policy?",
     "context": RETURNS, "expect": {"contains": "30 days"}},
    {"id": "R2", "time": "09:05", "kind": "order_status", "customer": "C-101", "question": "Where is my order?",
     "context": ORDERS["C-101"], "expect": {"contains": "#5521"}},
    {"id": "R3", "time": "09:11", "kind": "faq", "customer": "C-202", "question": "What is your return policy?",
     "context": RETURNS, "expect": {"contains": "30 days"}},
    {"id": "R4", "time": "09:15", "kind": "order_status", "customer": "C-202", "question": "Where is my order?",
     "context": ORDERS["C-202"], "expect": {"contains": "#5530"}},
    {"id": "R5", "time": "09:20", "kind": "complaint", "customer": "C-202",
     "question": "My lamp arrived broken. I attached a photo. What happens now?",
     "context": _complaint("C-202", "The photo shows the lamp's base cracked."), "expect": {"action": "replace"}},
    {"id": "R6", "time": "09:26", "kind": "complaint", "customer": "C-111",
     "question": "My mug arrived broken. I attached a photo. What happens now?",
     "context": _complaint("C-111", "The photo shows the handle broken off."),
     "expect": {"action": "refund"}},
    {"id": "R7", "time": "10:00", "kind": "faq", "customer": "C-303", "question": "Is there a Black Friday discount?",
     "context": PROMO_MORNING, "expect": {"contains": "20%"}},
    # 10:30: the rush. Six requests in the same minute.
    {"id": "R8", "time": "10:30", "kind": "chat", "customer": "C-404", "question": "hi!! anyone there?",
     "context": "", "expect": {"chat": True}},
    {"id": "R9", "time": "10:30", "kind": "chat", "customer": "C-505", "question": "Can you recommend a gift for my mum?",
     "context": "", "expect": {"chat": True}},
    {"id": "R10", "time": "10:30", "kind": "chat", "customer": "C-606", "question": "lol your site is slow today",
     "context": "", "expect": {"chat": True}},
    {"id": "R11", "time": "10:30", "kind": "faq", "customer": "C-707", "question": "Is there a Black Friday discount?",
     "context": PROMO_MORNING, "expect": {"contains": "20%"}},
    {"id": "R12", "time": "10:30", "kind": "complaint", "customer": "C-303",
     "question": "My rug came a week late. Do I get anything for that?",
     "context": _complaint("C-303", "Nothing was damaged."), "expect": {"action": "voucher"}},
    {"id": "R13", "time": "10:30", "kind": "order_status", "customer": "C-303", "question": "Where is my order?",
     "context": ORDERS["C-303"], "expect": {"contains": "#5544"}},
    {"id": "R14", "time": "11:40", "kind": "complaint", "customer": "C-808",
     "question": "The wool throw I received is torn along one edge. Photos attached. Please sort it out.",
     "context": _complaint("C-808", "The photos show a 10 cm tear."), "expect": {"action": "replace"}},
    {"id": "R15", "time": "12:30", "kind": "faq", "customer": "C-909", "question": "Is there a Black Friday discount?",
     "context": PROMO_NOON, "expect": {"contains": "25%"}},
]
OUTPUT = {"faq": Answer, "order_status": Answer, "chat": Answer, "complaint": Decision}
INSTRUCTIONS = {
    "faq": ("You answer customers of Ribeira Home, an online homeware shop. Answer in one or two sentences, only from the facts given. "
            "Keep numbers, percentages and codes exactly as they are written in the facts."),
    "order_status": "You answer a customer of Ribeira Home about their order, in one sentence, only from the facts given. Quote the order number.",
    "chat": "You are Ribeira Home's friendly support assistant. Reply in one short sentence. Do not promise anything.",
    "complaint": ("You decide what Ribeira Home does about a customer's complaint, applying the complaint policy in the facts "
                  "exactly, including its price limits. Give the action and a one-sentence reason that quotes the order number."),
}
ORDER_NUMBERS = {customer: re.search(r"#\d+", text).group(0) for customer, text in ORDERS.items()}


def similarity(a: str, b: str) -> float:
    """How alike two questions read (0 to 1), from their words. Real gateways use embeddings; the idea is the same."""
    wa, wb = Counter(re.findall(r"[a-z0-9-]+", a.lower())), Counter(re.findall(r"[a-z0-9-]+", b.lower()))
    dot = sum(wa[w] * wb[w] for w in wa)
    return round(dot / (sqrt(sum(v * v for v in wa.values())) * sqrt(sum(v * v for v in wb.values())) or 1), 2)


def minutes(clock: str) -> int:
    hours, mins = clock.split(":")
    return int(hours) * 60 + int(mins)


def clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def check(request: dict[str, Any], answer: Any) -> tuple[bool, str]:
    expect = request["expect"]
    if answer is None:
        return False, "no answer"
    text = answer.model_dump_json() if isinstance(answer, BaseModel) else str(answer)
    others = [number for customer, number in ORDER_NUMBERS.items() if customer != request["customer"] and number in text]
    if others:
        return False, f"LEAK: shows another customer's order ({', '.join(others)})"
    if isinstance(answer, Answer) and answer.text == BUSY_REPLY:
        ok = bool(expect.get("chat"))
        return ok, "declined politely" if ok else "declined: this customer needed an answer"
    if expect.get("chat"):
        return bool(text.strip()), "right"
    if "action" in expect:
        ok = isinstance(answer, Decision) and answer.action == expect["action"]
        return ok, "right" if ok else f"wrong: {getattr(answer, 'action', '?')} (policy says {expect['action']})"
    ok = expect["contains"] in text
    return ok, "right" if ok else f"wrong: does not say {expect['contains']}"


@dataclass
class Replay:
    chosen: Any
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    running: bool = False
    seconds: float = 0.0
    rate_limited: int = 0

    def start(self) -> threading.Thread:
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        began = time.monotonic()
        try:
            asyncio.run(self._main())
        except NotImplementedError:
            self.error = "Not written yet: starter/gateway.py. Write it, save the file and click Run again."
        except Exception as error:  # noqa: BLE001 - keep the page when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self) -> None:
        mine = load_starter("gateway")
        available = {size: patient(model) for size, model in models(self.chosen).items()}
        cache: list[dict[str, Any]] = []
        queue = sorted(({**r, "minute": minutes(r["time"]), "defers": 0} for r in REQUESTS), key=lambda r: r["minute"])
        calls: Counter[int] = Counter()  # provider A's calls per minute
        calls_today = 0
        while queue:
            request = queue.pop(0)
            began = time.monotonic()
            now = request["minute"]
            row = {"Request": request["id"], "Time": clock(now), "Kind": request["kind"], "Customer": request["customer"],
                   "Gateway": "", "Served by": "", "Result": "", "Cost $": 0.0, "Seconds": 0.0}
            usage = {"time": clock(now), "calls_this_minute": calls[now], "rate_limit": RATE_LIMIT, "calls_today": calls_today,
                     "waiting": [r["kind"] for r in queue if r["minute"] == now]}
            decision = mine.admit(_public(request), usage)
            if decision not in ("accept", "defer", "reject"):
                raise ValueError(f"admit() must return 'accept', 'defer' or 'reject', not {decision!r} (request {request['id']})")
            if decision == "defer" and request["defers"] < MAX_DEFERS:
                request["defers"] += 1
                request["minute"] = now + 1
                queue.append(request)
                queue.sort(key=lambda r: r["minute"])
                continue
            answer = None
            row["Gateway"] = (f"deferred {request['defers']}× → " if request["defers"] else "") + ("reject" if decision != "accept" else "accept")
            if decision != "accept":
                answer, row["Served by"] = Answer(text=BUSY_REPLY), "busy reply (no model)"
            else:
                hit = max(({**c, "similarity": similarity(c["request"]["question"], request["question"]), "order": i}
                           for i, c in enumerate(cache)), key=lambda c: (c["similarity"], c["order"]), default=None)
                if hit and mine.reuse(_public(request), {"request": _public(hit["request"]), "answer": hit["answer"],
                                                         "similarity": hit["similarity"]}):
                    answer, row["Served by"] = hit["answer"], f"cache (from {hit['request']['id']}, similarity {hit['similarity']})"
                else:
                    size = mine.route(_public(request))
                    if size not in ("none", "small", "large", "backup"):
                        raise ValueError(f"route() must return 'none', 'small', 'large' or 'backup', not {size!r} (request {request['id']})")
                    tried: list[str] = []
                    while size and answer is None:
                        tried.append(size)
                        if size in ("small", "large"):
                            calls[now] += 1
                        if size != "none":
                            calls_today += 1
                        answer, cost, problem = await self._ask(available, size, request, calls[now])
                        row["Cost $"] += cost
                        if problem:
                            if problem.startswith("429"):
                                self.rate_limited += 1
                            size = mine.on_error(_public(request), size, problem)
                            if size in tried:
                                size = None
                    row["Served by"] = " → ".join(tried) + ("" if answer is not None else " (failed)")
                    if answer is not None:
                        cache.append({"request": request, "answer": answer})
            ok, row["Result"] = check(request, answer)
            row["ok"] = ok
            row["Cost $"] = round(row["Cost $"], 5)
            row["Seconds"] = round(time.monotonic() - began, 2)
            self.rows.append(row)

    async def _ask(self, available: dict[str, Any], size: str, request: dict[str, Any], calls_now: int) -> tuple[Any, float, str | None]:
        if size == "none":
            if request["kind"] == "order_status":
                return Answer(text=ORDERS[request["customer"]]), 0.0, None
            return None, 0.0, "code has no answer for this kind of request: only order status is a lookup"
        if size not in available:
            return None, 0.0, f"unknown model {size!r}: use none, small, large or backup"
        if size in ("small", "large") and calls_now > RATE_LIMIT:
            await asyncio.sleep(0.3)
            return None, 0.0, f"429 Too Many Requests: provider A allows {RATE_LIMIT} calls a minute"
        if size == "large" and OUTAGE[0] <= clock(request["minute"]) < OUTAGE[1]:
            await asyncio.sleep(0.5)
            return None, 0.0, "503 Service Unavailable: provider A's large model is down"
        agent = Agent(available[size], output_type=OUTPUT[request["kind"]], instructions=INSTRUCTIONS[request["kind"]], retries=2,
                      name=f"{request['kind']}-{size}")
        result = await agent.run(f"Customer {request['customer']} asks: {request['question']}\nFacts: {request['context'] or 'none'}")
        usage = result.usage
        price_in, price_out = PRICES.get(model_name(models(self.chosen)[size]), PRICES["gpt-4.1-mini"])
        markup = BACKUP_MARKUP if size == "backup" else 1.0
        cost = ((usage.input_tokens or 0) * price_in + (usage.output_tokens or 0) * price_out) * markup / 1e6
        return result.output, cost, None

    def totals(self) -> dict[str, Any]:
        return {"right": sum(r["ok"] for r in self.rows), "cost": round(sum(r["Cost $"] for r in self.rows), 5),
                "cache": sum(r["Served by"].startswith("cache") for r in self.rows),
                "leaks": sum("LEAK" in r["Result"] for r in self.rows),
                "large": sum(r["Served by"].split(" → ")[0] == "large" for r in self.rows)}

    def verdict(self) -> list[tuple[bool, str]]:
        t = self.totals()
        failed = sum("(failed)" in r["Served by"] for r in self.rows)
        return [
            (t["right"] == len(REQUESTS), f"{t['right']} of {len(REQUESTS)} answers right"),
            (t["leaks"] == 0, "No customer saw another customer's order" if not t["leaks"] else f"{t['leaks']} answer(s) showed another customer's order"),
            (failed == 0, "Every request got an answer" if not failed else f"{failed} request(s) got no answer"),
            (self.rate_limited == 0, "Never hit the rate limit" if not self.rate_limited else f"Hit provider A's rate limit {self.rate_limited} time(s)"),
            (t["large"] <= 4, f"{t['large']} requests went first to the large model" + ("" if t["large"] <= 4 else ": most did not need it")),
        ]


def _public(request: dict[str, Any]) -> dict[str, Any]:
    """What your gateway sees of a request: no expected answer."""
    return {k: request[k] for k in ("id", "time", "kind", "customer", "question", "context")}

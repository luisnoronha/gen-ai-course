"""Exercise 2: an AI gateway in front of the incident team: routing, semantic cache and fallback.

A morning of the incident team is replayed: 12 requests to models, in order. Each goes through your gateway
(starter/gateway.py), which decides:
- route(request): which model answers it: "none" (code answers, no model), "small" or "large";
- reuse(request, hit): whether the most similar answer already in the cache can be served instead of calling a model;
- on_error(request, model, error): what to do when the model fails: another model, or None to give up.

The lab then checks every answer (is it right? did it leak something the requester may not see?), and adds up
cost and time. Request 10 meets an outage of the large model.
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

from common import PRICES, load_starter, model_name, models, patient
from pydantic import BaseModel
from pydantic_ai import Agent

OUTAGE = {"R10"}  # the large model answers 503 to these requests


class Triage(BaseModel):
    real: bool
    reason: str


class Diagnosis(BaseModel):
    cause: str
    action: Literal["rollback_change", "failover_site_B", "failover_site_C", "restart", "escalate"]
    target: str  # the change id or the site


class Summary(BaseModel):
    text: str


INC1 = ("INC-1 · order-gateway latency 185 ms since 10:08. The link order-gateway → reference-db is degraded. "
        "Recent changes: CHG-4750, a network ACL update between order-gateway (site A) and reference-db at 10:08. "
        "No other change. reference-db is healthy.")
INC2 = ("INC-2 · order-gateway latency 225 ms since 10:08. The link order-gateway → reference-db is degraded. "
        "Logs: carrier circuit CX-12 on site A has a fibre fault, repair at 14:00. Recent changes: CHG-4310, a deploy of "
        "order-gateway 2.4.0 at 09:50, unrelated (deployed before the problem, no errors). "
        "Planned work MRX-4790: reference-db on site B is in maintenance until 13:00; services on site B cannot reach it. "
        "Sites: A (primary), B (standby), C (disaster recovery, independent).")
OPEN_APPROVALS = "Open approvals: APR-014 (failover_gateway site-C, by on-call Rita), APR-015 (resend_confirmations batch-10:12)."
STATE = {"Where does order-gateway run now?": "order-gateway runs on site C since 10:41.",
         "Which approvals are open?": OPEN_APPROVALS}

ASK_DIAGNOSE = "What is the cause, and what should the team do now?"
REQUESTS: list[dict[str, Any]] = [
    {"id": "R1", "kind": "triage", "role": "on-call", "incident": "storm", "question": "Is this group of alerts a real incident?",
     "context": "6 alerts: order-gateway latency_high, severity critical, env prod. e.g. p99 latency 225 ms (threshold 50 ms).",
     "expect": {"real": True}},
    {"id": "R2", "kind": "triage", "role": "on-call", "incident": "storm", "question": "Is this group of alerts a real incident?",
     "context": "40 alerts: order-gateway heartbeat_missed, severity critical, env staging. e.g. staging order-gateway-2 missed 3 heartbeats.",
     "expect": {"real": False}},
    {"id": "R3", "kind": "lookup", "role": "on-call", "incident": "INC-2", "question": "Where does order-gateway run now?",
     "context": "", "expect": {"contains": "site C"}},
    {"id": "R4", "kind": "diagnose", "role": "on-call", "incident": "INC-1", "question": ASK_DIAGNOSE, "context": INC1,
     "expect": {"action": "rollback_change", "target": "CHG-4750"}},
    {"id": "R5", "kind": "summary", "role": "on-call", "incident": "INC-1", "question": "Write the handover note for the next shift.",
     "context": INC1 + " Action taken: rollback of CHG-4750 under APR-011. Recovered at 10:34.", "expect": {"contains": "INC-1"}},
    {"id": "R6", "kind": "diagnose", "role": "on-call", "incident": "INC-1", "question": ASK_DIAGNOSE, "context": INC1,
     "expect": {"action": "rollback_change", "target": "CHG-4750"}},
    {"id": "R7", "kind": "diagnose", "role": "on-call", "incident": "INC-2", "question": ASK_DIAGNOSE, "context": INC2,
     "expect": {"action": "failover_site_C", "target": "C"}},
    {"id": "R8", "kind": "summary", "role": "on-call", "incident": "INC-2", "question": "Summarise the incident.",
     "context": INC2 + " " + OPEN_APPROVALS + " Include the open approvals.", "expect": {"contains": "INC-2"}},
    {"id": "R9", "kind": "summary", "role": "member-support", "incident": "INC-2",
     "question": "Summarise the incident.",
     "context": "INC-2 · Orders were slow between 10:08 and 10:41 because of a network fault at a data centre. Service is back to normal.",
     "expect": {"contains": "INC-2", "no_internal": True}},
    {"id": "R10", "kind": "diagnose", "role": "on-call", "incident": "INC-2", "question": ASK_DIAGNOSE, "context": INC2,
     "expect": {"action": "failover_site_C", "target": "C"}},
    {"id": "R11", "kind": "triage", "role": "on-call", "incident": "storm", "question": "Is this group of alerts a real incident?",
     "context": "4 alerts: settlement confirmations_late, severity major, env prod. e.g. Order confirmations from order-gateway arriving late.",
     "expect": {"real": True}},
    {"id": "R12", "kind": "lookup", "role": "on-call", "incident": "INC-2", "question": "Which approvals are open?", "context": "",
     "expect": {"contains": "APR-014"}},
]
OUTPUT = {"triage": Triage, "diagnose": Diagnosis, "summary": Summary, "lookup": Summary}
INSTRUCTIONS = {
    "triage": "You triage alert groups at a stock exchange. Real only if members' orders, trades or settlement are affected in production now.",
    "diagnose": ("You are the incident diagnostician at Meridian Exchange. From the facts, give the cause and the one action to take now: "
                 "rollback_change (target: the change id) if a change caused it; failover_site_B or failover_site_C (target: the site letter) "
                 "if site A's network is failing and the site can be used; restart; or escalate."),
    "summary": "Write a short summary (3 sentences) for the requester, with the incident id. Use only the facts given.",
    "lookup": "Answer from the facts given, in one sentence.",
}


def similarity(a: str, b: str) -> float:
    """How alike two requests read (0 to 1), from their words. Real gateways use embeddings; the idea is the same."""
    wa, wb = Counter(re.findall(r"[a-z0-9-]+", a.lower())), Counter(re.findall(r"[a-z0-9-]+", b.lower()))
    dot = sum(wa[w] * wb[w] for w in wa)
    return round(dot / (sqrt(sum(v * v for v in wa.values())) * sqrt(sum(v * v for v in wb.values())) or 1), 2)


def check(request: dict[str, Any], answer: Any) -> tuple[bool, str]:
    expect = request["expect"]
    if answer is None:
        return False, "no answer"
    text = answer.model_dump_json() if isinstance(answer, BaseModel) else str(answer)
    if expect.get("no_internal") and re.search(r"APR-\d+|CHG-\d+|MRX-\d+|Rita", text):
        return False, "LEAK: internal details served to member support"
    if "real" in expect:
        ok = isinstance(answer, Triage) and answer.real == expect["real"]
        return ok, "right" if ok else f"wrong: real should be {expect['real']}"
    if "action" in expect:
        ok = isinstance(answer, Diagnosis) and answer.action == expect["action"] and expect["target"] in answer.target
        return ok, "right" if ok else f"wrong: {getattr(answer, 'action', '?')} {getattr(answer, 'target', '')}"
    ok = expect["contains"] in text
    return ok, "right" if ok else f"wrong: does not say {expect['contains']}"


@dataclass
class Replay:
    chosen: Any
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    running: bool = False
    seconds: float = 0.0

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
        for request in REQUESTS:
            began = time.monotonic()
            row = {"Request": request["id"], "Kind": request["kind"], "Who asks": request["role"], "Incident": request["incident"],
                   "Served by": "", "Result": "", "Cost $": 0.0, "Seconds": 0.0}
            answer = None
            # the most similar answer in the cache; between equals, the most recent
            hit = max(({**c, "similarity": similarity(c["request"]["question"], request["question"]), "order": i} for i, c in enumerate(cache)),
                      key=lambda c: (c["similarity"], c["order"]), default=None)
            if hit and mine.reuse(request, {"request": hit["request"], "answer": hit["answer"], "similarity": hit["similarity"]}):
                answer, row["Served by"] = hit["answer"], f"cache (from {hit['request']['id']}, similarity {hit['similarity']})"
            else:
                size = mine.route(request)
                tried: list[str] = []
                while size and answer is None:
                    tried.append(size)
                    answer, cost, problem = await self._ask(available, size, request)
                    row["Cost $"] += cost
                    if problem:
                        size = mine.on_error(request, size, problem)
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

    async def _ask(self, available: dict[str, Any], size: str, request: dict[str, Any]) -> tuple[Any, float, str | None]:
        if size == "none":
            answer = STATE.get(request["question"])
            return (Summary(text=answer) if answer else None), 0.0, None if answer else "code has no answer for this request"
        if size not in available:
            return None, 0.0, f"unknown model {size!r}"
        if size == "large" and request["id"] in OUTAGE:
            await asyncio.sleep(0.5)
            return None, 0.0, "503 Service Unavailable: the large model is overloaded"
        agent = Agent(available[size], output_type=OUTPUT[request["kind"]], instructions=INSTRUCTIONS[request["kind"]], retries=2,
                      name=f"{request['kind']}-{size}")
        result = await agent.run(f"Requester: {request['role']}.\nQuestion: {request['question']}\nFacts: {request['context']}")
        usage = result.usage
        price_in, price_out = PRICES.get(model_name(models(self.chosen)[size]), PRICES["gpt-4.1-mini"])
        return result.output, ((usage.input_tokens or 0) * price_in + (usage.output_tokens or 0) * price_out) / 1e6, None

    def totals(self) -> dict[str, Any]:
        return {"right": sum(r["ok"] for r in self.rows), "cost": round(sum(r["Cost $"] for r in self.rows), 5),
                "cache": sum(r["Served by"].startswith("cache") for r in self.rows),
                "leaks": sum("LEAK" in r["Result"] for r in self.rows)}

    def verdict(self) -> list[tuple[bool, str]]:
        t = self.totals()
        failed = sum("(failed)" in r["Served by"] for r in self.rows)
        large = sum(r["Served by"].split(" → ")[0] == "large" for r in self.rows)
        return [
            (t["right"] == len(REQUESTS), f"{t['right']} of {len(REQUESTS)} answers right"),
            (t["leaks"] == 0, "Nothing leaked to member support" if not t["leaks"] else f"{t['leaks']} answer(s) leaked internal details"),
            (failed == 0, "Every request got an answer" if not failed else f"{failed} request(s) failed (outage)"),
            (large <= 4, f"{large} requests went to the large model" + ("" if large <= 4 else ": most of them did not need it")),
        ]

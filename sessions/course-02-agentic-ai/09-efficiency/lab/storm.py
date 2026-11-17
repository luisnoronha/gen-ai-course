"""Exercise 2: an alert storm. 500 alerts in 5 minutes; one incident matters.

The lab gives each group of alerts your starter/storm.py produces to a triage agent (one model call per group),
in the order you choose, until the budget runs out. A group the triage agent calls "real" opens an incident for the
incident team, which costs INCIDENT_COST calls of the budget.

Limits:
- BUDGET model calls for the whole storm;
- RATE_LIMIT calls per minute at the provider: more than that waits for the next minute.
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from common import load_starter, patient
from pydantic import BaseModel
from pydantic_ai import Agent

BUDGET = 30
RATE_LIMIT = 8  # calls per minute
INCIDENT_COST = 10
REAL = {("order-gateway", "latency_high"), ("settlement", "confirmations_late")}


class Triage(BaseModel):
    real: bool  # needs the incident team now
    reason: str


def alerts(seed: int = 8) -> list[dict[str, Any]]:
    """The storm: 500 alerts between 10:00 and 10:05. Same every run."""
    rng = random.Random(seed)
    noise: list[dict[str, Any]] = []

    def add(n: int, component: str, rule: str, severity: str, env: str, source: str, messages: list[str]) -> None:
        for _ in range(n):
            noise.append({"component": component, "rule": rule, "severity": severity, "env": env, "source": source,
                          "message": rng.choice(messages)})

    add(300, "market-data", "cpu_high", "warning", "prod", "monitoring",
        [f"market-data-{i} CPU {p}% (threshold 80%)" for i in (1, 2, 3) for p in (81, 83, 85, 88)])
    add(100, "batch-reports", "disk_usage", "warning", "prod", "monitoring",
        [f"reports-{i}: disk {p}% used" for i in range(1, 9) for p in (81, 84, 86)])
    add(50, "member-portal", "login_slow", "minor", "prod", "member complaints",
        ["Member says login takes 5 seconds", "Portal login slow for a member", "Member cannot see statements quickly"])
    add(40, "order-gateway", "heartbeat_missed", "critical", "staging", "monitoring",
        ["staging order-gateway-2 missed 3 heartbeats", "staging order-gateway-1 missed heartbeat"])
    rng.shuffle(noise)
    real = ([{"component": "order-gateway", "rule": "latency_high", "severity": "critical", "env": "prod", "source": "monitoring",
              "message": f"order-gateway p99 latency {ms} ms (threshold 50 ms)"} for ms in (180, 210, 225, 230, 226, 228)]
            + [{"component": "settlement", "rule": "confirmations_late", "severity": "major", "env": "prod", "source": "settlement",
                "message": "Order confirmations from order-gateway arriving late; batch 10:12 delayed"} for _ in range(4)])
    storm = noise  # 490 alerts of noise
    for i, alert in enumerate(real):  # the 10 alerts that matter arrive late, between the others
        storm.insert(420 + i * 8, alert)
    for i, alert in enumerate(storm):
        alert["id"] = f"ALR-{5000 + i}"
        second = int(i * 300 / 500)
        alert["time"] = f"10:{second // 60:02d}:{second % 60:02d}"
    return storm


def summary(group: list[dict[str, Any]]) -> str:
    """What the triage agent reads about a group."""
    count = Counter((a["component"], a["rule"], a["severity"], a["env"]) for a in group)
    lines = [f"{len(group)} alerts, from {group[0]['time']} to {group[-1]['time']}."]
    lines += [f"- {n} × {c} {r} (severity {s}, env {e})" for (c, r, s, e), n in count.most_common(5)]
    lines += [f"  e.g. {a['source']}: {a['message']}" for a in group[:3]]
    return "\n".join(lines)


@dataclass
class Storm:
    model: Any
    alerts: list[dict[str, Any]] = field(default_factory=alerts)
    budget: int = BUDGET
    rows: list[dict[str, Any]] = field(default_factory=list)  # one per group looked at
    groups: int = 0
    minute: int = 0
    opened: list[str] = field(default_factory=list)
    found_at: str | None = None
    error: str | None = None
    running: bool = False
    seconds: float = 0.0

    @property
    def used(self) -> int:
        return BUDGET - self.budget

    @property
    def unseen(self) -> int:
        return len(self.alerts) - sum(row["alerts"] for row in self.rows)

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
            self.error = "Not written yet: starter/storm.py. Write it, save the file and click Run again."
        except Exception as error:  # noqa: BLE001 - keep the page when a run fails
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.seconds = round(time.monotonic() - began, 1)
            self.running = False

    async def _main(self) -> None:
        policy = load_starter("storm")
        groups = policy.order(policy.group([dict(a) for a in self.alerts]))
        self.groups = len(groups)
        triage = Agent(patient(self.model), output_type=Triage, instructions=policy.TRIAGE_INSTRUCTIONS, retries=3)
        queue = [g for g in groups if g]
        while queue and self.budget > 0:
            # One minute at the provider: at most RATE_LIMIT calls, run at the same time
            batch, queue = queue[:min(RATE_LIMIT, self.budget)], queue[min(RATE_LIMIT, self.budget):]
            self.budget -= len(batch)
            self.minute += 1
            verdicts = await asyncio.gather(*(triage.run(summary(g)) for g in batch))
            for group, verdict in zip(batch, verdicts, strict=True):
                self._record(group, verdict.output)

    def _record(self, group: list[dict[str, Any]], verdict: Triage) -> None:
        matters = any((a["component"], a["rule"]) in REAL and a["env"] == "prod" for a in group)
        opened = verdict.real and self.budget >= INCIDENT_COST
        if opened:
            self.budget -= INCIDENT_COST
            self.opened.append(group[0]["component"])
            if matters and self.found_at is None:
                self.found_at = f"minute {self.minute}"
        top = Counter(f"{a['component']} {a['rule']} ({a['env']})" for a in group).most_common(1)[0][0]
        self.rows.append({"Minute": self.minute, "Group": top, "Alerts": len(group), "Triage": "REAL" if verdict.real else "noise",
                          "Incident opened": "yes" if opened else ("no budget" if verdict.real else ""), "Reason": verdict.reason,
                          "alerts": len(group), "matters": matters})

    def verdict(self) -> list[tuple[bool, str]]:
        looked = any(row["matters"] for row in self.rows)
        false_alarms = sum(1 for row in self.rows if row["Incident opened"] == "yes" and not row["matters"])
        return [
            (self.found_at is not None, f"The incident that matters was opened ({self.found_at})" if self.found_at else
             ("The incident that matters was looked at, but not opened" if looked else "The incident that matters was never looked at")),
            (false_alarms == 0, "No incident opened for noise" if not false_alarms else f"{false_alarms} incidents opened for noise ({false_alarms * INCIDENT_COST} calls)"),
            (self.budget > 0, f"Budget left: {self.budget} of {BUDGET} calls" if self.budget > 0 else f"Budget spent: all {BUDGET} calls used"),
        ]

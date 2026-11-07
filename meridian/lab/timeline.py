"""What happened in a lab run: one event per step, with the agent that did it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from meridian.simulator import Simulator


@dataclass
class Timeline:
    sim: Simulator
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, agent: str, step: str, detail: Any = "") -> None:
        self.events.append({"time": self.sim.clock.label(self.sim.state.tick), "agent": agent, "step": step, "detail": detail})

    def by_agent(self) -> dict[str, list[dict[str, Any]]]:
        lanes: dict[str, list[dict[str, Any]]] = {}
        for event in self.events:
            lanes.setdefault(event["agent"], []).append(event)
        return lanes

"""The incident of the lab, and the one action the simulator does not have: moving the gateway to another site.

Sites: A (primary, where the gateway runs), B (standby), C (disaster recovery).
reference-db on site B is in planned maintenance (MRX-4790): a gateway on site B rejects orders.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from meridian.faults import ChangeFault, Effect, LinkFault
from meridian.simulator import Simulator
from meridian.tools import MeridianTools

HERE = Path(__file__).resolve().parent
INCIDENTS = {
    "INC-1 · A network change": HERE / "incidents" / "inc1.yaml",
    "INC-2 · Site A's network is failing": HERE / "incidents" / "inc2.yaml",
}
SITE_B_ERROR = 0.45
MAX_LATENCY_MS = 20
MAX_ERROR_RATE = 0.01


class World:
    def __init__(self, incident: str) -> None:
        self.incident = incident
        self.sim = Simulator(INCIDENTS[incident])
        self.tools = MeridianTools(self.sim, actor="incident-team")
        self.site = "A"
        self._left_behind: dict[int, LinkFault] = {}  # site A's network faults, paused while the gateway is elsewhere
        self.lock = threading.RLock()  # specialists work in parallel; the simulator is not thread-safe

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self.lock:
            return getattr(self.tools, name)(*args, **kwargs)

    def failover_gateway(self, site: str, approval_ref: str, actor: str) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            executor = self.sim.executor
            if site == self.site:
                return executor._record("failover_gateway", f"site-{site}", "rejected", f"The gateway already runs on site {site}.", False, None, actor, approval_ref).public()
            tick = self.sim.state.tick
            for fault in self.sim.faults:
                if fault.fault_id == "SITE-B":
                    fault.until = tick
                if site == "A":
                    continue
                if isinstance(fault, LinkFault) and fault.source == "order-gateway" and fault.until is None:
                    fault.until = tick  # the other sites do not use site A's network path
                    self._left_behind[tick] = fault
            if site == "A":  # back on site A: its network problem is still there, unless it was fixed meanwhile
                for paused_at, fault in self._left_behind.items():
                    if fault.until == paused_at:
                        fault.until = None
                self._left_behind.clear()
            if site == "B":
                self.sim.faults.append(ChangeFault("SITE-B", "change", tick, effects=[Effect("order-gateway", error_rate=SITE_B_ERROR, reason="reference-db site B refused the connection")]))
                self.sim.logs.add(self.sim.state, self.sim.clock, "order-gateway", "ERROR", "ERROR order rejected: reference-db site B connection refused (maintenance MRX-4790)", "order-gateway-1")
            self.site = site
            return executor._record("failover_gateway", f"site-{site}", "completed", f"order-gateway now serves from site {site}.", True, None, actor, approval_ref).public()

        with self.lock:
            return self.tools.record_call("failover_gateway", {"site": site}, run)

    def approve(self, action: str, target: str, reason: str, by: str) -> str:
        """Record an approval the on-call gave (a person in the lab, or 'auto'), so the simulator accepts the action."""
        with self.lock:
            return self.sim.request_approval(action, target, reason, "on-call", by)["approval_ref"]

    def gateway_now(self) -> dict[str, Any]:
        with self.lock:
            component = self.sim.state.component("order-gateway")
            return {"site": self.site, "latency_ms": round(component.latency_ms, 1), "error_rate": round(component.error_rate, 3)}

    def cause_left_behind(self) -> bool:
        """The gateway left site A while a change it could have rolled back still breaks site A."""
        with self.lock:
            return self.site != "A" and any(
                fault.until == paused_at and fault.change_id and self.sim.state.change(fault.change_id).active
                for paused_at, fault in self._left_behind.items())

    def recovered(self) -> bool:
        state = self.gateway_now()
        return state["latency_ms"] < MAX_LATENCY_MS and state["error_rate"] < MAX_ERROR_RATE

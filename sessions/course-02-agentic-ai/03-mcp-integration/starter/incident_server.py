"""Exercise 1 — Completed MCP server with correlation.

correlate finds the component of each event (from the text when the event does
not name one) and its kind of symptom (slow or errors). An event joins an open
incident when, within 30 minutes of its last event, the symptoms are compatible
and the component is the same, or shares a dependency and the symptom is errors.
Requests (no component, no symptom) always stay on their own.

The tool descriptions tell the model when to report an event and what it gets back.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from meridian.model import load_topology
from meridian.tools import MeridianTools

WINDOW_MINUTES = 30
DEPENDS_ON = {name: set(component.depends_on) for name, component in load_topology().components.items()}

# Words that point to a component, for events that do not name one (complaints, some tickets).
COMPONENT_WORDS = {
    "order-gateway": ["acknowledg", "order", "reject", "503", "gateway"],
    "market-data": ["quote", "market data", "feed", "price"],
    "settlement": ["settlement", "batch"],
}
# Symptom families. Memory pressure shows up as latency; a queue builds up with either.
SYMPTOM_WORDS = {
    "slow": ["latency", "slow", "late", "delay", "acknowledg", "memory"],
    "errors": ["error", "reject", "503", "fail", "refused"],
}


def component_of(event: dict[str, Any]) -> str | None:
    if event.get("component"):
        return event["component"]
    text = event["text"].lower()
    for component, words in COMPONENT_WORDS.items():
        if any(word in text for word in words):
            return component
    return None


def symptoms_of(event: dict[str, Any]) -> set[str]:
    text = event["text"].lower()
    if "queue" in text:
        return set(SYMPTOM_WORDS)
    return {family for family, words in SYMPTOM_WORDS.items() if any(word in text for word in words)}


def related(first: str, second: str) -> bool:
    """Two components share a dependency (e.g. order-gateway and settlement both depend on reference-db)."""
    return bool(DEPENDS_ON.get(first, set()) & DEPENDS_ON.get(second, set()))


def correlate(event: dict[str, Any], open_incidents: list[dict[str, Any]]) -> str | None:
    """Same incident when, within 30 minutes of its last event, the component is the same (or shares a dependency
    and the symptom is errors) and the symptoms are compatible. Events about no component or symptom (requests)
    always start their own incident."""
    component, symptoms = component_of(event), symptoms_of(event)
    if component is None or not symptoms:
        return None
    best: tuple[int, int, str] | None = None
    for incident in open_incidents:
        if event["time"] - incident["last_seen"] > WINDOW_MINUTES:
            continue
        incident_symptoms = set().union(*(symptoms_of(other) for other in incident["events"]))
        if not symptoms & incident_symptoms:
            continue
        components = set(incident["components"]) or {component_of(other) for other in incident["events"]} - {None}
        if component in components:
            strength = 2
        elif "errors" in symptoms and any(related(component, other) for other in components):
            strength = 1
        else:
            continue
        candidate = (strength, incident["last_seen"], incident["key"])
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else None


# The server -----------------------------------------------------------------


def _minutes(tools: MeridianTools, tick: int) -> int:
    return tools.sim.clock.minutes_at(tick) % (24 * 60)


def _open_incidents(tools: MeridianTools) -> dict[str, dict[str, Any]]:
    """Incident tickets already open when the run starts, in the shape `correlate` expects."""
    registry = {}
    for ticket in tools.sim.tickets.tickets:
        if ticket.project == "MRX" and ticket.issue_type == "Incident" and ticket.status not in ("Resolved", "Closed"):
            seen = _minutes(tools, ticket.created_tick)
            event = {"source": "ticket", "time": seen, "component": ticket.component, "text": f"{ticket.summary}. {ticket.description}"}
            registry[ticket.key] = {"key": ticket.key, "components": [ticket.component] if ticket.component else [], "first_seen": seen, "last_seen": seen, "events": [event]}
    return registry


def build_server(tools: MeridianTools) -> FastMCP:
    server = FastMCP("incidents", instructions="Registry of the incidents handled by the operations team.", version="0.1.0")
    registry = _open_incidents(tools)
    sim = tools.sim

    @server.tool(
        description=(
            "Report one event you are handling: the alert of the incident, a ticket or a member complaint. "
            "The server attaches it to the open incident it belongs to, or opens a new incident ticket. "
            "source: monitoring, ticket or complaint. component: the affected component if known. "
            "Returns the incident key and whether the event was attached to an existing incident. "
            "Call it once per event; do not create incident tickets yourself."
        ),
        run_in_thread=False,
    )
    def report_event(source: str, text: str, component: str | None = None) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            event = {"source": source, "time": _minutes(tools, sim.state.tick), "component": component, "text": text}
            key = correlate(event, list(registry.values()))
            if key in registry:
                incident = registry[key]
                incident["events"].append(event)
                incident["last_seen"] = event["time"]
                if component and component not in incident["components"]:
                    incident["components"].append(component)
                sim.tickets.comment(key, f"[{source}] {text}", tools.actor, sim.state.tick, sim.clock)
                return {"incident": key, "attached": True, "events_in_incident": len(incident["events"])}
            ticket = sim.tickets.create(
                {"project": "MRX", "issue_type": "Incident", "summary": text[:80], "description": f"[{source}] {text}", "component": component},
                tools.actor,
                sim.state.tick,
                sim.clock,
            )
            registry[ticket.key] = {"key": ticket.key, "components": [component] if component else [], "first_seen": event["time"], "last_seen": event["time"], "events": [event]}
            return {"incident": ticket.key, "attached": False, "new_incident": True}

        return tools.record_call("incidents.report_event", {"source": source, "text": text, "component": component}, run)

    @server.tool(description="List the incidents known to the server, with their components, first and last event time and number of events.", run_in_thread=False)
    def list_incidents() -> dict[str, Any]:
        def run() -> dict[str, Any]:
            return {"incidents": [{key: value for key, value in incident.items() if key != "events"} | {"events": len(incident["events"])} for incident in registry.values()]}

        return tools.record_call("incidents.list_incidents", {}, run)

    return server

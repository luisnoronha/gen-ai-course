"""Record a trace of the session 7 incident team with OpenTelemetry, and save it as JSON.

It runs in its own process (the lab starts it): the team of session 7 has its own modules.
Every agent, model call and tool call becomes a span with the OpenTelemetry GenAI attributes
(gen_ai.agent.name, gen_ai.operation.name, gen_ai.usage.input_tokens, gen_ai.tool.name, ...).

    python record.py --out trace.json --incident INC-2 --pattern pipeline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
S7 = HERE.parents[1] / "07-multi-agent" / "lab"
KEEP = ("gen_ai.operation.name", "gen_ai.agent.name", "gen_ai.request.model", "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens", "gen_ai.tool.name", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result",
        "gen_ai.output.messages", "final_result")
LONG = 400  # characters kept of a long attribute


def setup():
    """The session 7 team, with every agent named and every run traced."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from pydantic_ai import Agent
    from pydantic_ai.models.instrumented import InstrumentationSettings

    sys.path.insert(0, str(S7))
    import team

    exporter, provider = InMemorySpanExporter(), TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    Agent.instrument_all(InstrumentationSettings(tracer_provider=provider))
    build = team.build

    def named(name, room):
        agent = build(name, room)
        agent.name = name
        return agent

    team.build = named
    return team, exporter, provider.get_tracer("meridian.incident-team")


async def run(team, tracer, model, incident: str, pattern: str) -> Any:
    patterns = {"runbook": team.runbook, "pipeline": team.students_pipeline, "orchestrator": team.students_orchestrator}
    from world import INCIDENTS

    room = team.Team(model, next(name for name in INCIDENTS if name.startswith(incident)))
    if pattern == "orchestrator":
        load = team.load_starter

        def named_orchestrator(name):
            module = load(name)
            build = module.build_orchestrator

            def build_named(m):
                agent = build(m)
                agent.name = "orchestrator"
                return agent

            module.build_orchestrator = build_named
            return module

        team.load_starter = named_orchestrator
    with tracer.start_as_current_span(f"incident {incident}") as root:
        root.set_attribute("meridian.incident", incident)
        root.set_attribute("meridian.pattern", pattern)
        try:
            await room._main(patterns[pattern])
        finally:
            root.set_attribute("meridian.reported", room.reported)
            root.set_attribute("meridian.recovered", room.world.recovered())
            root.set_attribute("meridian.gateway", json.dumps(room.world.gateway_now()))
    return room


def spans(exporter, model_label: str | None = None) -> list[dict[str, Any]]:
    finished = sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)
    start = finished[0].start_time if finished else 0
    out = []
    for span in finished:
        attributes = {}
        for key, value in span.attributes.items():
            if key in KEEP or key.startswith("meridian."):
                text = value if isinstance(value, (int, float, bool)) else str(value)
                attributes[key] = text[:LONG] if isinstance(text, str) else text
        name = span.name
        if model_label and str(attributes.get("gen_ai.request.model", "")).startswith("function"):
            attributes["gen_ai.request.model"] = model_label
            name = f"chat {model_label}"
        out.append({"name": name, "trace_id": f"{span.context.trace_id:032x}", "span_id": f"{span.context.span_id:016x}",
                    "parent_id": f"{span.parent.span_id:016x}" if span.parent else None,
                    "start_ms": round((span.start_time - start) / 1e6, 1), "end_ms": round((span.end_time - start) / 1e6, 1),
                    "status": span.status.status_code.name, "error": span.status.description, "attributes": attributes})
    return out


def record(model, incident: str, pattern: str, title: str, source: str, model_label: str | None = None) -> dict[str, Any]:
    team, exporter, tracer = setup()
    began = time.time()
    asyncio.run(run(team, tracer, model, incident, pattern))
    return {"title": title, "source": source, "recorded_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(began)),
            "spans": spans(exporter, model_label)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--incident", default="INC-2")
    parser.add_argument("--pattern", default="pipeline", choices=["runbook", "pipeline", "orchestrator"])
    args = parser.parse_args()
    from meridian.agent_runtime import default_model

    trace = record(default_model(), args.incident, args.pattern, f"Live run · {args.incident} · {args.pattern}", "a live run with the real model")
    Path(args.out).write_text(json.dumps(trace, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

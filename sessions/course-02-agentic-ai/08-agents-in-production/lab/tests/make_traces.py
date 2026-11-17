"""Generate the recorded traces of exercise 2 (lab/traces/*.json). Run it again only to change them:

    uv run --locked python sessions/course-02-agentic-ai/08-agents-in-production/lab/tests/make_traces.py

Each trace runs the session 7 team with a scripted model. Trace 2 replays a failure seen with gpt-4.1-mini while building
session 7; traces 3 and 4 are failures built for the exercise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[1] / "07-multi-agent" / "lab" / "tests"))
import record
from fake import scripted
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

SOURCES = {
    "t1": "Scripted model: a healthy run",
    "t2": "Scripted model: replays a failure seen with gpt-4.1-mini while building session 7",
    "t3": "Scripted model: a failure built for the exercise",
    "t4": "Scripted model: a failure built for the exercise",
}


def instructions(messages) -> str:
    return next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""


def database_in_circles():
    normal = scripted().function
    names = ["reference-db", "settlement", "market-data", "matching-engine", "order-gateway"]

    def play(messages, info):
        if instructions(messages).startswith("You are the database specialist"):
            n = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
            return ModelResponse(parts=[ToolCallPart("read_logs" if n % 2 else "read_metrics", {"component": names[n % len(names)]})])
        return normal(messages, info)

    return FunctionModel(play)


def lost_change_id():
    normal = scripted().function

    def play(messages, info):
        response = normal(messages, info)
        part = response.parts[0]
        if instructions(messages).startswith("You are the network specialist") and part.tool_name == info.output_tools[0].name:
            return ModelResponse(parts=[ToolCallPart(part.tool_name, {
                "cause": "A recent network ACL update degraded the link from order-gateway to reference-db",
                "evidence": ["link degraded", "ACL update on order-gateway at 10:08"]})])
        return response

    return FunctionModel(play)


def asks_everything_twice():
    normal = scripted().function

    def play(messages, info):
        if instructions(messages).startswith("You are the incident orchestrator"):
            asked = [p.tool_name for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
            if asked.count("ask_network") < 2:
                question = "What causes the latency?" if not asked else "Double-check: are you sure about the cause? Look again at everything."
                return ModelResponse(parts=[ToolCallPart("ask_network", {"question": question}),
                                            ToolCallPart("ask_database", {"question": question})])
        return normal(messages, info)

    return FunctionModel(play)


TRACES = [
    ("t1", "Trace 1 · INC-1 · runbook", scripted(), "INC-1", "runbook", False,
     "Healthy. Network found CHG-4750, remediation rolled it back, the gateway recovered. Nothing should fire."),
    ("t2", "Trace 2 · INC-2 · pipeline", database_in_circles(), "INC-2", "pipeline", True,
     ("The database specialist went round in circles (read_metrics/read_logs on every component) and stopped without an answer. "
     "So nobody told remediation that site B is in maintenance: it failed over to site B and reported 'resolved' with 45% errors.")),
    ("t3", "Trace 3 · INC-1 · runbook", lost_change_id(), "INC-1", "runbook", True,
     ("The network specialist found the ACL change but did not quote its id (CHG-4750). Remediation could not roll back an "
     "unnamed change, failed over to site B instead and reported 'resolved'. The gateway did not recover.")),
    ("t4", "Trace 4 · INC-2 · orchestrator", asks_everything_twice(), "INC-2", "orchestrator", True,
     ("The incident was resolved, but the orchestrator asked both specialists everything twice ('double-check'): "
     "about twice the model calls and tokens needed. A cost problem, not a correctness one.")),
]


def main() -> None:
    out = LAB / "traces"
    out.mkdir(exist_ok=True)
    index = []
    for name, title, model, incident, pattern, should_fire, truth in TRACES:
        # each trace in a fresh process state: the recorder patches the team module
        for module in [m for m in sys.modules if m in ("team", "world")]:
            del sys.modules[module]
        trace = record.record(model, incident, pattern, title, SOURCES[name], model_label="gpt-4.1-mini")
        (out / f"{name}.json").write_text(json.dumps(trace, indent=1), encoding="utf-8")
        index.append({"file": f"{name}.json", "title": title, "should_fire": should_fire, "what_happened": truth})
        print(name, len(trace["spans"]), "spans")
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

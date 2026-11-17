"""Scripted models for session 9: no API key needed. The small one gets the hard diagnosis wrong."""

from __future__ import annotations

import re

from pydantic_ai.messages import (
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

COMPONENTS = ["order-gateway", "matching-engine", "market-data", "settlement", "reference-db"]
SCRIPT = """for c in ["order-gateway", "matching-engine", "market-data", "settlement", "reference-db"]:
    m = read_metrics(c)
    print(c, m["latency_ms"], m["error_rate"])
for c in ["matching-engine", "market-data", "settlement", "reference-db"]:
    print("link", c, check_link("order-gateway", c).get("state", "no link"))
"""


def scripted(size: str = "large") -> FunctionModel:
    def play(messages, info: AgentInfo) -> ModelResponse:
        prompt = " ".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        tools = {t.name for t in info.function_tools}
        if "run_python" in tools:  # code mode
            if not returns:
                return ModelResponse(parts=[ToolCallPart("run_python", {"code": SCRIPT})])
            return ModelResponse(parts=[TextPart("Unhealthy: " + str(returns[-1].content)[:200])])
        if "read_metrics" in tools:  # tools one by one
            calls = [("read_metrics", {"component": c}) for c in COMPONENTS] + [("check_link", {"source": "order-gateway", "target": c}) for c in COMPONENTS[1:]]
            if len(returns) < len(calls):
                name, args = calls[len(returns)]
                return ModelResponse(parts=[ToolCallPart(name, args)])
            return ModelResponse(parts=[TextPart("Unhealthy: order-gateway latency; link to reference-db degraded.")])
        output = info.output_tools[0]
        fields = set(output.parameters_json_schema.get("properties", {}))
        if fields == {"real", "reason"}:
            real = bool(re.search(r"order-gateway latency_high|settlement confirmations_late", prompt)) and "staging" not in prompt
            return ModelResponse(parts=[ToolCallPart(output.name, {"real": real, "reason": "orders affected" if real else "noise"})])
        if "action" in fields:
            if "CHG-4750" in prompt and "fibre" not in prompt:
                args = {"cause": "CHG-4750 ACL change", "action": "rollback_change", "target": "CHG-4750"}
            elif size == "large":
                args = {"cause": "site A carrier fault; site B in maintenance", "action": "failover_site_C", "target": "C"}
            else:  # the small model misses the maintenance window
                args = {"cause": "site A carrier fault", "action": "failover_site_B", "target": "B"}
            return ModelResponse(parts=[ToolCallPart(output.name, args)])
        facts = prompt.split("Facts:", 1)[-1].strip()
        if not facts:
            return ModelResponse(parts=[ToolCallPart(output.name, {"text": "I have no facts to answer this."})])
        incident = re.search(r"INC-\d", facts)
        approvals = " ".join(re.findall(r"APR-\d+", facts)) if "Include the open approvals" in facts else ""
        text = f"{incident.group(0) if incident else ''}: {facts.split('.')[0]}. {approvals}".strip()
        return ModelResponse(parts=[ToolCallPart(output.name, {"text": text})])

    return FunctionModel(play)


def both() -> dict[str, FunctionModel]:
    return {"small": scripted("small"), "large": scripted("large")}

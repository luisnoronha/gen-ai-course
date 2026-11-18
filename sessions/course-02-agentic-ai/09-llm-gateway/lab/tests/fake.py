"""Scripted models for session 9: no API key needed. The small one misses the complaint policy's price limit."""

from __future__ import annotations

import re

from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


def scripted(size: str = "large") -> FunctionModel:
    def play(messages, info: AgentInfo) -> ModelResponse:
        prompt = " ".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        output = info.output_tools[0]
        facts = prompt.split("Facts:", 1)[-1].strip()
        order = re.search(r"#\d+", facts)
        if "action" in output.parameters_json_schema.get("properties", {}):
            price = int(re.search(r"€(\d+)\)", facts).group(1))
            if "late" in prompt and "Nothing was damaged" in facts:
                action = "voucher"
            elif size == "large":
                action = "refund" if price < 80 else "replace"
            else:  # the small model misses the €80 limit
                action = "refund"
            return ModelResponse(parts=[ToolCallPart(output.name, {"action": action, "reason": f"Order {order.group(0)}: policy."})])
        if facts == "none":
            return ModelResponse(parts=[ToolCallPart(output.name, {"text": "Hello! How can I help you today?"})])
        return ModelResponse(parts=[ToolCallPart(output.name, {"text": facts.split(". ")[0] + "."})])

    return FunctionModel(play)


def both() -> dict[str, FunctionModel]:
    return {"small": scripted("small"), "large": scripted("large")}

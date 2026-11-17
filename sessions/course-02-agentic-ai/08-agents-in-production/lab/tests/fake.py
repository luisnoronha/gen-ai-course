"""A scripted model that plays every agent of the lab, for tests without an API key."""

from __future__ import annotations

import re
import time

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

STEP = re.compile(r"(failover_gateway|resend_confirmations) (site-[ABC]|batch-[\d:]+)([^\n]*)")


def scripted(delay: float = 0.0) -> FunctionModel:
    def play(messages, info: AgentInfo) -> ModelResponse:
        time.sleep(delay)
        instructions = next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""
        prompt = " ".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        output = info.output_tools[0].name if info.output_tools else "final_result"

        def call(name, args):
            return ModelResponse(parts=[ToolCallPart(name, args)])

        if instructions.startswith("You are the remediation"):
            steps = STEP.findall(prompt)
            done = [p for p in returns if p.tool_name in ("failover_gateway", "resend_confirmations")]
            if len(done) < len(steps):
                action, target, rest = steps[len(done)]
                found = re.search(r"idempotency_key=([^,\s]+)", rest)
                key = found.group(1) if found else None
                ref = re.search(r"(APR-\d+)", rest)
                args = {"idempotency_key": key or f"resume/{action}/{target}", "reason": "resume",
                        "approval_ref": ref.group(1) if ref and "no approval" not in rest else None}
                if action == "failover_gateway":
                    args["site"] = target[-1]
                else:
                    args["batch"] = target
                return call(action, args)
            return call(output, {"status": "done", "actions": [f"{p.tool_name}: {p.content.get('outcome')}" for p in done], "summary": "Plan carried out."})
        if instructions.startswith("You are the reviewer"):
            names = [p.tool_name for p in returns]
            if "gateway_state" not in names:
                return call("gateway_state", {})
            if "history" not in names:
                return call("history", {})
            state = next(p.content for p in returns if p.tool_name == "gateway_state")
            history = next(p.content for p in returns if p.tool_name == "history")
            targets = [(e["action"], e["target"]) for e in history]
            return call(output, {"recovered": state["latency_ms"] < 20 and state["error_rate"] < 0.01,
                                 "clean": len(targets) == len(set(targets)), "reason": "Checked state and history."})
        if instructions.startswith("You are the Settlement team's agent"):
            batch = re.search(r"batch-\d\d:\d\d", prompt)
            ref = re.search(r"APR-\d+", prompt)
            incident = re.search(r"INC-\d+", prompt)
            return call(output, {"batch": batch.group(0) if batch else None, "approval_ref": ref.group(0) if ref else None,
                                 "incident": incident.group(0) if incident else None})
        # the trace analyst: answers in text
        if "recovered=False" in prompt:
            return ModelResponse(parts=[TextPart("Outcome: not fixed. Root cause: see the path.")])
        return ModelResponse(parts=[TextPart("Outcome: the team reported it resolved.")])

    return FunctionModel(play)

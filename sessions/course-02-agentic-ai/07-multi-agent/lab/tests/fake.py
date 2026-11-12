"""A scripted model that plays every agent of the lab, for tests without an API key."""

from __future__ import annotations

import json
import time

from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


def scripted(delay: float = 0.0) -> FunctionModel:
    def play(messages, info: AgentInfo) -> ModelResponse:
        time.sleep(delay)
        instructions = next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""
        prompt = " ".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        done = [p.tool_name for p in returns]
        seen = json.dumps([p.content for p in returns], default=str)
        output = info.output_tools[0].name if info.output_tools else "final_result"

        def call(*calls):
            return ModelResponse(parts=[ToolCallPart(name, args) for name, args in calls])

        def answer(**fields):
            return call((output, fields))

        if instructions.startswith("You are the network specialist"):
            if "check_link" not in done:
                return call(("check_link", {"source": "order-gateway", "target": "reference-db"}), ("recent_changes", {"component": "order-gateway"}))
            if "read_logs" not in done:
                return call(("read_logs", {"component": "order-gateway", "contains": "WARN"}))
            if '"active": true' in seen and "CHG-4750" in seen:
                return answer(cause="CHG-4750 (network ACL) degraded the link to reference-db", evidence=["CHG-4750", "link degraded"], constraints=[])
            return answer(cause="Site A carrier circuit CX-12 is losing packets; no change to roll back", evidence=["CX-12 fibre fault", "link degraded"], constraints=[])
        if instructions.startswith("You are the database specialist"):
            if "search_tickets" not in done:
                return call(("search_tickets", {"component": "reference-db"}))
            if "read_ticket" not in done:
                return call(("read_ticket", {"key": "MRX-4790"}))
            return answer(cause="reference-db on site A is healthy", evidence=["MRX-4790"], constraints=["reference-db site B is in maintenance until 13:00: do not fail over to site B (MRX-4790)"])
        if instructions.startswith("You are the remediation specialist"):
            rejected = [p for p in returns if isinstance(p.content, dict) and str(p.content.get("status", "")).startswith("rejected")]
            acted = [p for p in returns if p.tool_name in ("rollback_change", "failover_gateway") and not (isinstance(p.content, dict) and str(p.content.get("status", "")).startswith("rejected"))]
            if acted and "gateway_state" not in done[done.index(acted[-1].tool_name):]:
                return call(("gateway_state", {}))
            if acted:
                state = [p.content for p in returns if p.tool_name == "gateway_state"][-1]
                ok = state["error_rate"] < 0.01 and state["latency_ms"] < 20
                return answer(status="resolved" if ok else "resolved", actions=[f"{p.tool_name}" for p in acted], summary=f"Gateway on site {state['site']}.")
            avoid_b = any(word in prompt for word in ("maintenance", "MRX-4790", "site B")) or any("B" in str(p.content.get("comment", "")) for p in rejected)
            if "CHG-4750" in prompt and "rollback_change" not in done:
                return call(("rollback_change", {"change_id": "CHG-4750", "reason": "CHG-4750 degraded the link"}))
            site = "C" if avoid_b or rejected else "B"
            return call(("failover_gateway", {"site": site, "reason": "Site A network is failing"}))
        if instructions.startswith("You are the reviewer"):
            if "gateway_state" not in done:
                return call(("gateway_state", {}))
            if "read_logs" not in done:
                return call(("read_logs", {"component": "order-gateway", "contains": "ERROR"}))
            state = [p.content for p in returns if p.tool_name == "gateway_state"][-1]
            ok = state["error_rate"] < 0.01 and state["latency_ms"] < 20
            return answer(recovered=ok, reason="Healthy." if ok else f"{state['error_rate']:.0%} errors on site {state['site']}: reference-db site B refuses connections (maintenance MRX-4790).")
        # the orchestrator
        if "ask_network" not in done:
            return call(("ask_network", {"question": "What causes the gateway latency?"}), ("ask_database", {"question": "Is reference-db healthy? Planned work?"}))
        if "ask_remediation" not in done:
            findings = "\n".join(str(p.content) for p in returns)
            return call(("ask_remediation", {"task": f"Mitigate. Findings:\n{findings}"}))
        report = [str(p.content) for p in returns if p.tool_name == "ask_remediation"][-1]
        return answer(status="resolved" if report.startswith("resolved") else "unresolved", root_cause="see findings", summary=report[:200])

    return FunctionModel(play)

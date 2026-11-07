"""Run the incident team with a scripted model that plays every agent: no API key needed."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
STARTER = LAB.parent / "starter"
REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-07"
sys.path.insert(0, str(LAB))
import team as team_module
from team import Team


def scripted(messages, info):
    instructions = next(m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions)
    prompt = next(p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart))
    returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
    done = [p.tool_name for p in returns]
    tools = {tool.name for tool in info.function_tools}
    output = info.output_tools[0].name

    def call(*calls):
        return ModelResponse(parts=[ToolCallPart(name, args) for name, args in calls])

    def answer(**args):
        return ModelResponse(parts=[ToolCallPart(output, args)])

    if instructions.startswith("You are the incident commander"):
        if "investigate" not in done:
            return call(("investigate", {"domain": "network", "question": "Why is the gateway slow?"}),
                        ("investigate", {"domain": "database", "question": "Is reference-db healthy?"}))
        findings = " ".join(str(p.content) for p in returns if p.tool_name == "investigate")
        if "remediate" not in done and "remediate_goal" not in done:
            if "remediate" in tools:
                schema = next(t for t in info.function_tools if t.name == "remediate").parameters_json_schema
                fields = schema["properties"]  # PydanticAI flattens a single model argument into the tool's fields
                contract = {name: (["rollback_change CHG-4750"] if name == "allowed_actions" else ["site B in maintenance (MRX-4790): no failover"] if name == "constraints" else 1 if name == "plan_version" else "Fix the gateway latency.") for name in fields}
                return call(("remediate", contract))
            return call(("remediate_goal", {"goal": "Fix the gateway latency."}))
        if "verify" in tools and done.count("verify") < 1:
            return call(("verify", {}))
        retried = any("verifier has not confirmed" in str(getattr(p, "content", "")) for m in messages for p in m.parts)
        return answer(status="unresolved" if retried else "resolved", root_cause="CHG-4750", actions=[], open_risks=[], summary="Scripted.")

    if instructions.startswith("You are the network specialist"):
        if not done:
            return call(("check_link", {"source": "order-gateway", "target": "reference-db"}), ("recent_changes", {"component": "order-gateway"}))
        return answer(domain="network", hypothesis="CHG-4750 degraded the link", evidence=["CHG-4750"], constraints=[])

    if instructions.startswith("You are the database specialist"):
        if not done:
            return call(("read_ticket", {"key": "MRX-4790"}))
        return answer(domain="database", hypothesis="reference-db healthy", evidence=["MRX-4790"], constraints=["site B in maintenance until 13:00"])

    if instructions.startswith("You are the remediation specialist"):
        if not done:
            if "maintenance" in prompt:
                return call(("rollback_change", {"change_id": "CHG-4750"}))
            if "raise_alert_threshold" in tools and "judged only" in instructions:
                return call(("raise_alert_threshold", {"component": "order-gateway"}))
            return call(("request_approval", {"action": "failover_gateway", "target": "site-B", "reason": "standard mitigation"}))
        if done[-1] == "request_approval":
            return call(("failover_gateway", {"site": "B", "approval_ref": returns[-1].content["approval_ref"]}))
        if done.count("read_metrics") < 3:
            return call(("read_metrics", {"component": "order-gateway"}))
        return answer(status="resolved", actions=done, evidence=[])

    if instructions.startswith("You are the independent verifier"):
        if "state_checks" not in done:
            return call(("read_metrics", {"component": "order-gateway"}), ("state_checks", {}))
        checks = next(p.content for p in returns if p.tool_name == "state_checks")
        return answer(recovered=not checks.get("problems") and "note" not in checks, reason=str(checks))
    raise AssertionError(instructions[:60])


MODEL = FunctionModel(scripted)


@pytest.fixture
def solutions():
    """Use the reference solutions as the students' files, then restore the starter files."""
    saved = {name: (STARTER / name).read_text(encoding="utf-8") for name in ("contracts.py", "verifier.py")}
    for name in saved:
        shutil.copy(REFERENCE / name, STARTER / name)
    yield
    for name, text in saved.items():
        (STARTER / name).write_text(text, encoding="utf-8")


def healthy(team: Team) -> bool:
    state = team.world.gateway_now()
    return state["latency_ms"] < 20 and state["error_rate"] < 0.01 and state["link to reference-db"] == "up"


def test_without_controls_the_lost_constraint_breaks_the_mitigation():
    team = Team(MODEL)
    team.run()
    assert team.error is None, team.error
    assert team.world.site == "B"
    assert team.outcome.status == "resolved" and not healthy(team)  # false "resolved"
    assert team.messages[-1] == {"to": "remediation", "message": "Fix the gateway latency."}


def test_starter_contract_with_only_a_goal_still_loses_the_constraint():
    team = Team(MODEL, {"contracts": True})
    team.run()
    assert team.error is None, team.error
    assert "maintenance" not in team.messages[-1]["message"]
    assert team.world.site == "B"


def test_reference_contract_carries_the_constraint(solutions):
    team = Team(MODEL, {"contracts": True})
    team.run()
    assert team.error is None, team.error
    assert "maintenance" in team.messages[-1]["message"]
    assert team.world.site == "A" and team.world.sim.executor.effects("rollback_change", "CHG-4750")
    team.world.sim.advance(3)
    assert healthy(team)


def test_gaming_is_caught_by_the_verifier(solutions):
    gamed = Team(MODEL, {"alert_goal": True})
    gamed.run()
    assert gamed.world.threshold_changes and gamed.outcome.status == "resolved" and not healthy(gamed)
    checked = Team(MODEL, {"alert_goal": True, "verifier": True})
    checked.run()
    assert checked.error is None, checked.error
    assert checked.world.threshold_changes
    assert checked.outcome.status == "unresolved"
    assert any("thresholds" in str(v) for v in checked.verifications)


def test_least_privilege_removes_the_threshold_tool():
    team = Team(MODEL, {"alert_goal": True, "least_privilege": True})
    team.run()
    assert not team.world.threshold_changes


def test_failover_needs_a_matching_approval():
    from world import World
    world = World()
    assert world.failover_gateway("B", None, "test")["status"] == "rejected"
    ref = world.tools.request_approval("failover_gateway", "site-B", "test")["approval_ref"]
    assert world.failover_gateway("B", ref, "test")["status"] == "completed"
    world.sim.advance(3)
    assert world.gateway_now()["error_rate"] > 0.3


def test_app_runs_the_team():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = MODEL
    at.run()
    assert not at.exception
    at.button(key="run_team").click().run()
    assert not at.exception
    assert len(at.session_state["s07_runs"]) == 1
    at.toggle(key="switch_verifier").set_value(True).run()
    at.button(key="run_team").click().run()
    assert not at.exception
    at.button(key="guide").click().run()
    assert not at.exception

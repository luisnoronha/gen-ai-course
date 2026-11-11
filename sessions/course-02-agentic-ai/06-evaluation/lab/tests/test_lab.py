"""Run the lab with a scripted model: no API key needed."""

from __future__ import annotations

import importlib.util
import shutil
import sys

import pytest
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
import agents
import critic
import loop
import suite
from pydantic_ai.messages import ModelRequest


def scripted(messages, info):
    """Plays every agent: the incident agent (a simple script), the critic and the proposer."""
    returned = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
    prompt = next(part.content for message in messages for part in message.parts if isinstance(part, UserPromptPart))
    instructions = next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""
    output_fields = info.output_tools[0].parameters_json_schema.get("properties", {}) if info.output_tools else {}
    if "fix_hint" in output_fields:  # the critic
        bad = "FAIL" in prompt or ("resolved" in prompt.lower() and "restarted" not in prompt.lower() and "restart_instance" not in prompt)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"acceptable": not bad, "score": 2 if bad else 4,
                                                                         "problem": "claims without evidence" if bad else "none", "fix_hint": "check the state"})])
    if instructions.startswith("You improve the instructions"):  # the proposer
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"change": "Check links and recent changes before acting.",
                                                                         "instructions": agents.A_INSTRUCTIONS, "verify_recovery": True})])

    def call(name, **args):
        return ModelResponse(parts=[ToolCallPart(name, args)])

    def report(status, evidence):
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "incident_id": "INC", "status": status, "root_cause": "scripted", "actions_taken": [], "evidence": evidence,
            "summary": f"Scripted run: {status}."})])

    last = returned[-1] if returned else None
    if last is None:
        alert = prompt.split("Related alert: ")[1].rstrip(".")
        return call("read_alert", alert_id=alert)
    names = [part.tool_name for part in returned]
    if last.tool_name == "read_alert":
        return call("read_metrics", component=last.content["component"])
    if last.tool_name == "read_metrics":
        if "error" in last.content:
            return report("insufficient_information", [])
        ref = last.content["source_ref"]
        if "restart_instance" in names:
            return report("resolved", [ref])
        instances = last.content["readings"][-1].get("instances", {})
        hot = [name for name, instance in instances.items() if instance["memory_pct"] > 90]
        if hot:
            return call("restart_instance", instance_id=hot[0], idempotency_key="k1")
        return report("unresolved", [ref])
    if last.tool_name == "restart_instance":
        return call("read_metrics", component="order-gateway")
    return ModelResponse(parts=[TextPart("done")])


MODEL = FunctionModel(scripted)


@pytest.fixture
def solutions():
    """Use the reference solutions as the students' files, then restore the starter files."""
    names = ("trajectory.py", "decision.py", "improver.py")
    saved = {name: (agents.STARTER / name).read_text(encoding="utf-8") for name in names}
    for name in names:
        shutil.copy(REPO / "private/course-02-agentic-ai/reference/session-06" / name, agents.STARTER / name)
    yield
    for name, text in saved.items():
        (agents.STARTER / name).write_text(text, encoding="utf-8")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_suite_runs_every_case_in_parallel():
    cases = suite.cases()
    assert {"s01-gateway-latency", "s02-firewall-change"} <= set(cases)
    jobs = [(agents.B, case, path) for case, path in cases.items()]
    results = suite.run_many(jobs, MODEL)
    assert len(results) == len(cases)
    by_case = {r.case: r for r in results}
    assert by_case["s01-gateway-latency"].passed, by_case["s01-gateway-latency"].failed
    assert not by_case["s02-firewall-change"].passed  # a restart does not fix a firewall change
    assert all(note == "not written yet" for r in results for note in r.trajectory.values())
    table = suite.pass_table(results)
    assert table[-1]["Case"] == "TOTAL"


def test_version_a_checks_recovery_in_code():
    result = suite.run_one(agents.A, "s01-gateway-latency", suite.cases()["s01-gateway-latency"], MODEL)
    assert result.status in ("resolved", "unresolved")


def test_reference_trajectory_checks():
    reference = load(REPO / "private/course-02-agentic-ai/reference/session-06/trajectory.py", "ref_trajectory")
    from meridian.agent_runtime import run_incident
    run = run_incident(agents.harness(agents.B), suite.cases()["s01-gateway-latency"], model=MODEL, use_memory=False)
    assert reference.fresh_evidence_before_resolved(run)[0]
    assert reference.evidence_is_real(run)[0]
    run.report = run.report.model_copy(update={"evidence": ["metrics/order-gateway/999"]})
    assert not reference.evidence_is_real(run)[0]
    run.trace = [call for call in run.trace if not (call.tool == "read_metrics" and call.step > 3)]
    assert not reference.fresh_evidence_before_resolved(run)[0]


def test_reference_decision():
    ref = load(REPO / "private/course-02-agentic-ai/reference/session-06/decision.py", "ref_decision")
    C = ref.CaseComparison
    assert ref.decide([C("x", 1, 1, 1, 1)], 100, 50).adopt is None
    assert ref.decide([C("x", 3, 3, 2, 3), C("y", 0, 3, 3, 3)], 100, 50).adopt is False
    assert ref.decide([C("x", 3, 3, 3, 3), C("y", 0, 3, 3, 3)], 100, 100).adopt is True
    assert ref.decide([C("x", 3, 3, 3, 3)], 100, 100).adopt is False


def test_critic_reviews_every_text():
    reviews, origin = critic.review_all(MODEL, "prompt", ["Status: resolved.", "Restarted order-gateway-2. Resolved."])
    assert origin == "default"
    assert [r.acceptable for r in reviews] == [False, True]


def test_critic_sees_only_the_agents_words_until_improver_is_written():
    result = suite.run_one(agents.B, "s01-gateway-latency", suite.cases()["s01-gateway-latency"], MODEL)
    assert result.description.startswith("Status reported by the agent")


def test_loop_iterates_keeps_memory_and_tests_reserved(solutions):
    state = loop.Loop(agents.B, "prompt", "checks", repetitions=1)
    attempt = state.step(MODEL, lambda text: None)
    assert attempt.iteration == 1 and attempt.change
    assert state.lessons and "#1" in state.lessons[0]
    assert "WHAT THE AGENT DID" in state.best.results[0].description
    assert set(state.who.values()) == {"yours"}  # every piece came from the students' improver.py
    state.step(MODEL, lambda text: None)
    assert len(state.attempts) == 2
    assert "#2" in state.memory_text()
    first, best = state.test_reserved(MODEL, lambda text: None)
    assert {r.case for r in first.results} == set(loop.RESERVED)


def test_loop_can_accept_by_critic_score():
    state = loop.Loop(agents.B, "prompt", "critic", repetitions=1)
    attempt = state.step(MODEL, lambda text: None)
    assert "critic score" in attempt.reason
    assert state.memory_text().startswith("(no memory")
    assert state.who["proposer agent"] == "default"


def test_app_two_tabs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=120)
    at.session_state["model"] = MODEL
    at.run()
    assert not at.exception
    at.multiselect(key="cases").set_value(["s01-gateway-latency", "s01-stale-alert"])
    at.button(key="run_suite").click().run()
    assert not at.exception
    assert len(at.session_state["s06_results"]) == 4
    assert len(at.tabs) == 2
    at.number_input(key="loop_reps").set_value(1)
    at.button(key="loop_one").click().run()
    assert not at.exception
    assert len(at.session_state["s06_loop"].attempts) == 1
    at.button(key="loop_test").click().run()
    assert not at.exception
    assert at.session_state["s06_loop"].reserved is not None
    at.button(key="guide").click().run()
    assert not at.exception


def test_students_agent_becomes_version_c():
    assert "C (yours)" not in agents.versions()  # the starter is blank
    saved = (agents.STARTER / "my_agent.py").read_text(encoding="utf-8")
    shutil.copy(REPO / "private/course-02-agentic-ai/reference/session-06/my_agent.py", agents.STARTER / "my_agent.py")
    try:
        found = agents.versions()
        assert "C (yours)" in found
        c = found["C (yours)"]
        result = suite.run_one(c, "s01-gateway-latency", suite.cases()["s01-gateway-latency"], MODEL)
        assert result.version == "C (yours)"  # the fake model never checks links, so the guard blocks its restart
        state = loop.Loop(c, "prompt", "critic", repetitions=1)
        state.step(MODEL, lambda text: None)
        assert state.attempts[0] and state.best.version.builder is c.builder
    finally:
        (agents.STARTER / "my_agent.py").write_text(saved, encoding="utf-8")

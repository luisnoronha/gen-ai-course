"""Run the lab with a scripted model: no API key needed."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
import agents
import judge
import suite


def scripted(messages, info):
    """A simple agent: read the alert and metrics, restart an instance above 90% memory, read again, report."""
    returned = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
    prompt = next(part.content for message in messages for part in message.parts if isinstance(part, UserPromptPart))
    if info.output_tools and info.output_tools[0].name == "final_result" and "SUMMARY:" in prompt:
        accepted = "resolved" not in prompt.split("SUMMARY:")[1].lower() or "restarted" in prompt.lower()
        return ModelResponse(parts=[ToolCallPart("final_result", {"acceptable": accepted, "score": 4 if accepted else 2, "reason": "scripted"})])

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


def test_judge_and_agreement():
    items = [{"facts": "f", "summary": "Incident resolved."}, {"facts": "f", "summary": "Restarted order-gateway-2. Resolved."}]
    verdicts = judge.judge_all(MODEL, "prompt", items)
    counts = judge.agreement([False, True], verdicts)
    assert counts["agree"] == 2


def test_app_runs_suite_and_judge():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = MODEL
    at.run()
    assert not at.exception
    at.multiselect(key="cases").set_value(["s01-gateway-latency", "s01-stale-alert"])
    at.button(key="run_suite").click().run()
    assert not at.exception
    assert len(at.session_state["s06_results"]) == 4
    for item in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"):
        at.radio(key=f"label_{item}").set_value("No")
    at.run()
    at.button(key="run_judge").click().run()
    assert not at.exception
    at.button(key="guide").click().run()
    assert not at.exception

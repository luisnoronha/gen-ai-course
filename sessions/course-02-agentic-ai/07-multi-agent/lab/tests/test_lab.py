"""Run the lab with a scripted model: no API key needed."""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "tests"))
import team as T
from fake import scripted
from world import INCIDENTS

INC1, INC2 = list(INCIDENTS)
REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-07"


@pytest.fixture
def solutions():
    names = ("pipeline.py", "orchestrator.py")
    saved = {name: (T.STARTER / name).read_text(encoding="utf-8") for name in names}
    for name in names:
        shutil.copy(REFERENCE / name, T.STARTER / name)
    yield
    for name, text in saved.items():
        (T.STARTER / name).write_text(text, encoding="utf-8")


def run(team: T.Team, pattern) -> T.Team:
    team.start(pattern).join(60)
    assert not team.running
    return team


def test_runbook_works_on_inc1_and_fails_on_inc2():
    first = run(T.Team(scripted(), INC1), T.runbook)
    assert first.world.recovered() and first.reported == "resolved", first.error
    second = run(T.Team(scripted(), INC2), T.runbook)
    assert second.world.site == "B" and not second.world.recovered()
    assert second.reported == "resolved"  # a false "resolved": nobody checked
    assert "database" not in second.cards
    assert [m["kind"] for m in second.feed].count("approved") == 1


def test_lab_solutions_runs_the_reference_without_touching_starter(monkeypatch):
    before = (T.STARTER / "orchestrator.py").read_text(encoding="utf-8")
    monkeypatch.setenv("LAB_SOLUTIONS", "1")
    team = run(T.Team(scripted(), INC2), T.students_orchestrator)
    assert team.error is None and team.world.recovered()
    assert (T.STARTER / "orchestrator.py").read_text(encoding="utf-8") == before


def test_an_agent_that_goes_round_in_circles_does_not_stop_the_team(solutions):
    from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    normal = scripted().function

    def looping(messages, info):
        instructions = next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""
        if instructions.startswith("You are the database specialist"):
            return ModelResponse(parts=[ToolCallPart("search_tickets", {"text": "maintenance"})])
        return normal(messages, info)

    team = run(T.Team(FunctionModel(looping), INC1), T.students_pipeline)
    assert team.error is None, team.error
    assert team.cards["database"]["status"] == "error" and "stopped without finishing" in team.cards["database"]["activity"]
    assert team.cards["remediation"]["status"] == "done"
    database_tools = [m["text"] for m in team.feed if m["kind"] == "tool" and m["from"] == "database"]
    assert len(database_tools) == T.MAX_STEPS
    assert sum("refused" in text for text in database_tools) == T.MAX_STEPS - T.MAX_TOOL_CALLS


def test_an_invented_component_name_is_refused_and_the_agent_goes_on():
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ToolCallPart,
    )
    from pydantic_ai.models.function import FunctionModel

    normal = scripted().function

    def inventing(messages, info):
        instructions = next((m.instructions for m in messages if isinstance(m, ModelRequest) and m.instructions), "") or ""
        retried = any(isinstance(p, RetryPromptPart) for m in messages for p in m.parts)
        if instructions.startswith("You are the database specialist") and not retried:
            return ModelResponse(parts=[ToolCallPart("read_metrics", {"component": "reference-db-site-B"})])
        return normal(messages, info)

    team = T.Team(FunctionModel(inventing), INC1)
    import asyncio
    answer = asyncio.run(team.ask("database", "Is there planned work?"))
    assert "MRX-4790" in answer and team.cards["database"]["status"] == "done"


def test_every_tool_call_is_on_the_board():
    team = run(T.Team(scripted(), INC2), T.runbook)
    tools = [m["text"] for m in team.feed if m["kind"] == "tool"]
    assert any(text.startswith("check_link order-gateway") for text in tools)
    assert any(text.startswith("gateway_state") for text in tools)


def test_world_knows_when_the_cause_was_left_behind():
    def failover(world, site):
        world.failover_gateway(site, world.approve("failover_gateway", f"site-{site}", "test", "test"), "test")

    world = T.World(INC1)
    failover(world, "C")
    assert world.recovered() and world.cause_left_behind()  # moved away, CHG-4750 still breaks site A
    world.call("rollback_change", "CHG-4750", idempotency_key="t", confirmation_ref=world.approve("rollback_change", "CHG-4750", "test", "test"))
    assert not world.cause_left_behind()
    world = T.World(INC2)
    failover(world, "B")
    failover(world, "A")
    assert not world.recovered()  # back on site A: its network is still failing


def test_starters_say_they_are_not_written(tmp_path, monkeypatch):
    for name in ("pipeline", "orchestrator"):
        (tmp_path / f"{name}.py").write_text(
            "async def run_pipeline(team):\n    raise NotImplementedError('starter/pipeline.py')\n"
            "def build_orchestrator(model):\n    raise NotImplementedError('starter/orchestrator.py')\n", encoding="utf-8")
    monkeypatch.setattr(T, "STARTER", tmp_path)
    for pattern in (T.students_pipeline, T.students_orchestrator):
        team = run(T.Team(scripted(), INC1), pattern)
        assert team.error and team.error.startswith("Not written")


def test_reference_pipeline_and_orchestrator(solutions):
    for pattern in (T.students_pipeline, T.students_orchestrator):
        for incident in INCIDENTS:
            team = run(T.Team(scripted(), incident), pattern)
            assert team.error is None, team.error
            assert team.world.recovered(), (pattern.__name__, incident, team.world.gateway_now())
            assert {"network", "database", "remediation"} <= set(team.cards)
    orchestrator = run(T.Team(scripted(), INC2), T.students_orchestrator)
    assert orchestrator.outcome and orchestrator.cards["orchestrator"]["status"] == "done"
    assert orchestrator.requests > 0 and orchestrator.tokens > 0


def test_specialists_work_in_parallel(solutions):
    team = T.Team(scripted(delay=0.3), INC2)
    seen = set()
    thread = team.start(T.students_orchestrator)
    while thread.is_alive():
        working = {name for name, card in team.cards.items() if card["status"] == "working"}
        if {"network", "database"} <= working:
            seen.add("both")
        time.sleep(0.05)
    assert "both" in seen


def test_person_rejects_and_reviewer_catches():
    # The person rejects site B with a comment: remediation changes the plan
    team = T.Team(scripted(), INC2, approvals="human")
    thread = team.start(T.runbook)
    for _ in range(200):
        if team.pending:
            break
        time.sleep(0.05)
    assert team.pending["target"] == "site-B"
    first = team.pending
    team.answer(False, "Site B is in maintenance (MRX-4790).")
    for _ in range(200):
        if team.pending and team.pending is not first:
            break
        time.sleep(0.05)
    assert team.pending["target"] == "site-C"
    team.answer(True)
    thread.join(30)
    assert team.world.site == "C" and team.world.recovered()
    # Auto-approve, plus the reviewer: it rejects site B and remediation fixes it
    team = run(T.Team(scripted(), INC2, reviewer=True), T.runbook)
    assert team.world.site == "C" and team.world.recovered() and team.reported == "resolved"
    assert any(m["from"] == "reviewer" and m["text"].startswith("Not recovered") for m in team.feed)


def test_app_runs_every_tab(solutions):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = scripted()
    at.run()
    assert not at.exception
    assert len(at.tabs) == 3
    for key in ("pipeline", "orchestrator", "demo"):
        at.button(key=f"run_{key}").click().run()
        team = at.session_state[f"team_{key}"]
        for _ in range(200):
            if not team.running:
                break
            time.sleep(0.05)
        at.run()
        assert not at.exception, at.exception
    assert len(at.session_state["runs"]) == 3
    at.button(key="guide").click().run()
    assert not at.exception

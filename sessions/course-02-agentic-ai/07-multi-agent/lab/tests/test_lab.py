"""Run the lab with a scripted model: no API key needed."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "tests"))
import team as T  # noqa: E402
from fake import scripted  # noqa: E402
from world import INCIDENTS  # noqa: E402

INC1, INC2 = list(INCIDENTS)
REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-07"


@pytest.fixture
def solutions():
    names = ("pipeline.py", "commander.py")
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


def test_starters_say_they_are_not_written():
    for pattern in (T.students_pipeline, T.students_commander):
        team = run(T.Team(scripted(), INC1), pattern)
        assert team.error and team.error.startswith("Not written")


def test_reference_pipeline_and_commander(solutions):
    for pattern in (T.students_pipeline, T.students_commander):
        for incident in INCIDENTS:
            team = run(T.Team(scripted(), incident), pattern)
            assert team.error is None, team.error
            assert team.world.recovered(), (pattern.__name__, incident, team.world.gateway_now())
            assert {"network", "database", "remediation"} <= set(team.cards)
    commander = run(T.Team(scripted(), INC2), T.students_commander)
    assert commander.outcome and commander.cards["commander"]["status"] == "done"
    assert commander.requests > 0 and commander.tokens > 0


def test_specialists_work_in_parallel(solutions):
    team = T.Team(scripted(delay=0.3), INC2)
    seen = set()
    thread = team.start(T.students_commander)
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
    for key in ("pipeline", "commander", "demo"):
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

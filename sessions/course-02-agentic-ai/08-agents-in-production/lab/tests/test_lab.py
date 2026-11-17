"""Run the lab with a scripted model: no API key needed."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "tests"))
import a2a as A
import room as R
import traces as TR
import workers as W
from fake import scripted

REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-08"


@pytest.fixture
def naive():
    names = ("resume.py", "a2a_client.py", "monitors.py")
    saved = {name: (R.STARTER / name).read_text(encoding="utf-8") for name in names}
    yield
    for name, text in saved.items():
        (R.STARTER / name).write_text(text, encoding="utf-8")


@pytest.fixture
def solutions(naive):
    for name in ("resume.py", "a2a_client.py", "monitors.py"):
        shutil.copy(REFERENCE / name, R.STARTER / name)


@pytest.fixture(autouse=True)
def fast(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "STEP_DELAY", 0)
    monkeypatch.setattr(R, "RUNS", tmp_path)
    monkeypatch.setattr(W, "STEP", 0.05)
    monkeypatch.setattr(W, "LEASE", 0.2)
    monkeypatch.setattr(A, "WORK_SECONDS", 0.3)


def run(thing):
    thing.start().join(60)
    assert not thing.running
    assert thing.error is None, thing.error
    return thing


def ok(checks):
    return {text: good for good, text in checks}


def test_naive_resume_repeats_the_resend(naive):
    room = run(R.Room(scripted(), "after_resend"))
    assert room.crashed and room.world.count("resend_confirmations") == 2
    assert not all(good for good, _ in room.verdict())
    checkpoint = R.json.loads(room.path.read_text(encoding="utf-8"))
    assert checkpoint["plan"][1]["status"] == "started"  # saved before acting, never updated: the crash


def test_naive_resume_uses_an_expired_approval(naive):
    room = run(R.Room(scripted(), "long_pause"))
    assert room.world.count("resend_confirmations") == 1
    assert any("no longer valid" in v for v in room.world.violations)


def test_reference_resume_is_clean_in_both_scenarios(solutions):
    for scenario in R.SCENARIOS.values():
        room = run(R.Room(scripted(), scenario))
        assert all(good for good, _ in room.verdict()), (scenario, room.verdict())
        assert any(m["kind"] == "note" for m in room.feed)


def test_naive_a2a_client_resends_three_times(naive):
    run_ = run(A.A2ARun(scripted()))
    assert run_.world.count("resend_confirmations") == 3 and len(run_.server.tasks) == 3
    assert not all(good for good, _ in run_.verdict())


def test_reference_a2a_client_is_clean(solutions):
    run_ = run(A.A2ARun(scripted()))
    assert all(good for good, _ in run_.verdict()), run_.verdict()
    states = [m["text"] for m in run_.feed if m["from"] == "settlement" and "TASK_STATE_INPUT_REQUIRED" in m["text"]]
    assert states  # it went through input-required and answered in the same task


def test_a2a_server_needs_the_token_and_dedupes_keys():
    import asyncio

    world = R.World()
    server = A.SettlementAgent(scripted(), world, lambda *a: None)
    send = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {"message": {"role": "ROLE_USER", "parts": [
        {"text": "Resend batch-10:12, approval APR-001"}, {"data": {"idempotency_key": "k"}}]}}}
    assert "error" in asyncio.run(server.handle(send, None))
    first = asyncio.run(server.handle(send, A.TOKEN))["result"]["task"]
    again = asyncio.run(server.handle(send, A.TOKEN))["result"]["task"]
    assert first["id"] == again["id"] and len(server.tasks) == 1


def test_traces_naive_monitors_miss_and_reference_catches(naive):
    review = run(TR.Review(scripted()))
    caught = [text for good, text in review.verdict() if good]
    # only the run that raised an exception (the database's usage limit) is caught; the other problems raise nothing
    assert len(caught) == 2 and any(text.startswith("Trace 2") for text in caught)


def test_traces_reference(solutions):
    review = run(TR.Review(scripted()))
    assert all(good for good, _ in review.verdict()), review.verdict()
    assert all(row["analyst"] for row in review.rows)


def test_recorded_traces_have_the_genai_spans():
    for trace, _ in TR.recorded():
        operations = {s["operation"] for s in trace.spans}
        assert {"invoke_agent", "chat", "execute_tool"} <= operations
        assert trace.root["incident"] in ("INC-1", "INC-2") and TR.waterfall_rows(trace)


def test_world_rules():
    world = R.World()
    ref = world.approve("resend_confirmations", R.BATCH, "x", "t")
    assert world.resend_confirmations(R.BATCH, "k1", ref, "t")["outcome"] == "completed"
    assert world.resend_confirmations(R.BATCH, "k1", ref, "t")["outcome"] == "already_done"
    assert world.count("resend_confirmations") == 1
    world.pause(20)
    assert not world.approval_status(ref)["valid"]
    world2 = R.World()
    ref2 = world2.approve("failover_gateway", "site-C", "x", "t")
    world2.pause(41)  # the session opens at 11:00
    assert "before the trading session opened" in world2.approval_status(ref2)["reason"]


@pytest.mark.parametrize(("mode", "crash", "clean"), [("memory", False, False), ("shared", False, True), ("shared", True, True), ("memory", True, False)])
def test_workers(mode, crash, clean):
    fleet = run(W.Fleet(mode, crash=crash))
    assert all(good for good, _ in fleet.verdict()) == clean, fleet.verdict()


def test_app_runs_every_tab(solutions):
    import time

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = scripted()
    at.run()
    assert not at.exception
    assert len(at.tabs) == 4
    for key, state in (("run_a2a", "a2a"), ("run_review", "review"), ("run_room", "room"), ("run_fleet", "fleet")):
        at.button(key=key).click().run()
        for _ in range(400):
            if not at.session_state[state].running:
                break
            time.sleep(0.05)
        at.run()
        assert not at.exception, at.exception
    assert len(at.session_state["runs"]) == 3
    at.button(key="guide").click().run()
    assert not at.exception

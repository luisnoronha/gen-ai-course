"""Run the lab with scripted models: no API key needed."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[3]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "tests"))
import common
import gateway as G
from fake import both

REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-09"


@pytest.fixture
def naive(monkeypatch):
    monkeypatch.setattr(common, "STARTER", Path(__file__).parent / "naive")


@pytest.fixture
def solutions(monkeypatch):
    monkeypatch.setattr(common, "STARTER", REFERENCE)


def run(replay):
    replay.start().join(60)
    assert not replay.running
    assert replay.error is None, replay.error
    return replay


def served(replay):
    return {row["Request"]: row for row in replay.rows}


def test_naive_gateway_shows_every_problem(naive):
    replay = run(G.Replay(both()))
    rows = served(replay)
    assert rows["R4"]["Served by"].startswith("cache (from R2") and "LEAK" in rows["R4"]["Result"]  # C-101's order to C-202
    assert rows["R6"]["Served by"].startswith("cache (from R5") and rows["R6"]["Result"].startswith("LEAK")
    assert "(failed)" in rows["R12"]["Served by"] and replay.rate_limited == 1  # the rush: the complaint loses its call
    assert "(failed)" in rows["R14"]["Served by"]  # the outage
    assert rows["R15"]["Result"].startswith("wrong")  # yesterday's discount from the cache
    assert not all(ok for ok, _ in replay.verdict())


def test_reference_gateway_is_all_green(solutions):
    replay = run(G.Replay(both()))
    assert all(ok for ok, _ in replay.verdict()), (replay.verdict(), replay.rows)
    rows = served(replay)
    assert rows["R3"]["Served by"].startswith("cache") and rows["R11"]["Served by"].startswith("cache")
    assert rows["R10"]["Gateway"].startswith("deferred") and rows["R14"]["Served by"] == "large → backup"
    assert [row["Request"] for row in replay.rows].index("R10") > [row["Request"] for row in replay.rows].index("R13")


def test_small_model_gets_complaints_wrong(solutions, monkeypatch):
    mine = common.load_starter("gateway")
    monkeypatch.setattr(mine, "route", lambda request: "none" if request["kind"] == "order_status" else "small")
    monkeypatch.setattr(G, "load_starter", lambda name: mine)
    rows = served(run(G.Replay(both())))
    assert rows["R5"]["Result"].startswith("wrong")


def test_defer_has_a_limit(solutions, monkeypatch):
    mine = common.load_starter("gateway")
    monkeypatch.setattr(mine, "admit", lambda request, usage: "defer" if request["kind"] == "chat" else "accept")
    monkeypatch.setattr(G, "load_starter", lambda name: mine)
    rows = served(run(G.Replay(both())))
    assert rows["R8"]["Result"] == "declined politely" and rows["R8"]["Gateway"].startswith("deferred 3×")


def test_similarity():
    assert G.similarity("Where is my order?", "Where is my order?") == 1.0
    assert G.similarity("My lamp arrived broken. I attached a photo. What happens now?",
                        "My mug arrived broken. I attached a photo. What happens now?") >= 0.8


def test_app_runs(solutions):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = both()
    at.run()
    assert not at.exception
    at.button(key="run_replay").click().run()
    for _ in range(600):
        if not at.session_state["replay"].running:
            break
        time.sleep(0.05)
    at.run()
    assert not at.exception, at.exception
    assert len(at.session_state["runs"]) == 1
    at.button(key="guide").click().run()
    assert not at.exception


def test_a_wrong_return_value_says_what_is_expected(solutions, monkeypatch):
    mine = common.load_starter("gateway")
    monkeypatch.setattr(mine, "route", lambda request: "medium")
    monkeypatch.setattr(G, "load_starter", lambda name: mine)
    replay = G.Replay(both())
    replay.start().join(60)
    assert replay.error and "route() must return" in replay.error

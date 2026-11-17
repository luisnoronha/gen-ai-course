"""Run the lab with scripted models: no API key needed."""

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
import codemode as C
import common
import gateway as G
import storm as S
from fake import both, scripted

REFERENCE = REPO / "private/course-02-agentic-ai/reference/session-09"
NAMES = ("storm.py", "gateway.py")


@pytest.fixture
def naive():
    saved = {name: (common.STARTER / name).read_text(encoding="utf-8") for name in NAMES}
    yield
    for name, text in saved.items():
        (common.STARTER / name).write_text(text, encoding="utf-8")


@pytest.fixture
def solutions(naive):
    for name in NAMES:
        shutil.copy(REFERENCE / name, common.STARTER / name)


def run(thing):
    thing.start().join(60)
    assert not thing.running
    assert thing.error is None, thing.error
    return thing


def test_naive_storm_never_sees_the_incident(naive):
    storm = run(S.Storm(scripted("small")))
    assert storm.used == S.BUDGET and storm.found_at is None


def test_reference_storm_finds_it_with_budget_left(solutions):
    storm = run(S.Storm(scripted("small")))
    assert all(good for good, _ in storm.verdict()), storm.verdict()


def test_naive_gateway(naive):
    replay = run(G.Replay(both()))
    totals = replay.totals()
    assert totals["right"] < len(G.REQUESTS) and totals["leaks"] >= 1
    served = {row["Request"]: row["Served by"] for row in replay.rows}
    assert served["R7"].startswith("cache (from R4")  # INC-2 served INC-1's diagnosis: same words, other incident


def test_reference_gateway(solutions):
    replay = run(G.Replay(both()))
    assert all(good for good, _ in replay.verdict()), (replay.verdict(), replay.rows)
    assert replay.totals()["cache"] >= 1


def test_small_model_gets_the_hard_diagnosis_wrong(solutions, monkeypatch):
    import s09_gateway  # noqa: F401  (loaded by the run above)

    replay = G.Replay(both())
    mine = common.load_starter("gateway")
    monkeypatch.setattr(mine, "route", lambda request: "small" if request["kind"] != "lookup" else "none")
    monkeypatch.setattr(common, "load_starter", lambda name: mine)
    monkeypatch.setattr(G, "load_starter", lambda name: mine)
    run(replay)
    assert next(row for row in replay.rows if row["Request"] == "R7")["Result"].startswith("wrong")


def test_similarity():
    assert G.similarity("Summarise the incident.", "Summarise the incident.") == 1.0
    assert G.similarity("Where does order-gateway run now?", "Which approvals are open?") < 0.5


def test_code_mode_uses_fewer_model_calls():
    duel = C.Duel(scripted())
    duel.start().join(60)
    assert duel.error is None, duel.error
    tools, code = duel.results["Tools, one by one"], duel.results["Code mode"]
    assert code["Model calls"] < tools["Model calls"] and duel.scripts


def test_sandbox_blocks_imports_and_loops():
    systems = C.Systems()
    assert "ImportError" in C.blocked_example(systems) or "__import__" in C.blocked_example(systems)
    assert "Stopped" in C.sandbox("while True:\n    pass", systems)
    assert "order-gateway" in C.sandbox("print(read_metrics('order-gateway'))", systems)


def test_app_runs_every_tab(solutions):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(LAB / "app.py"), default_timeout=60)
    at.session_state["model"] = both()
    at.run()
    assert not at.exception
    assert len(at.tabs) == 3
    for key, state in (("run_storm", "storm"), ("run_replay", "replay"), ("run_duel", "duel")):
        at.button(key=key).click().run()
        for _ in range(600):
            if not at.session_state[state].running:
                break
            time.sleep(0.05)
        at.run()
        assert not at.exception, at.exception
    assert len(at.session_state["runs"]) == 2
    at.button(key="guide").click().run()
    assert not at.exception

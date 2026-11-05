"""Checks for the simulator itself. Run with: uv run python -m pytest meridian/tests"""

from __future__ import annotations

from pathlib import Path

import pytest

from meridian import MeridianTools, Simulator, load_scenario
from meridian.evaluate import evaluate

REPO = Path(__file__).resolve().parents[2]
S1 = REPO / "sessions" / "course-02-agentic-ai" / "01-agent-harness" / "cases"
S2 = REPO / "sessions" / "course-02-agentic-ai" / "02-context-tools-skills" / "cases"
S3 = REPO / "sessions" / "course-02-agentic-ai" / "03-mcp-integration" / "cases"
ALL_CASES = sorted((REPO / "sessions" / "course-02-agentic-ai").glob("*/cases/*.yaml"))


@pytest.mark.parametrize("path", ALL_CASES, ids=lambda path: path.stem)
def test_every_case_loads_and_opens_its_alert(path: Path) -> None:
    sim = Simulator(path)
    brief = sim.incident_brief()
    assert brief["alert_id"] is not None
    assert sim.state.tick == sim.scenario.warmup_ticks


def test_same_seed_gives_same_signals() -> None:
    first = Simulator(S2 / "s02-noisy-gateway.yaml")
    second = Simulator(S2 / "s02-noisy-gateway.yaml")
    assert first.logs.lines == second.logs.lines
    assert first.metrics.history == second.metrics.history


def test_memory_leak_raises_latency_and_restart_only_helps_for_a_while() -> None:
    sim = Simulator(S1 / "s01-gateway-latency.yaml")
    tools = MeridianTools(sim)
    assert sim.state.component("order-gateway").latency_ms > 100
    tools.restart_instance("order-gateway-2")
    sim.advance(3)
    assert sim.state.component("order-gateway").latency_ms < 20
    sim.advance(130)
    assert sim.state.component("order-gateway").latency_ms > 100


def test_each_tool_call_moves_time_by_a_fixed_step() -> None:
    sim = Simulator(S1 / "s01-gateway-latency.yaml")
    tools = MeridianTools(sim)
    start = sim.state.tick
    tools.read_metrics("order-gateway")
    tools.read_metrics("order-gateway")
    assert sim.state.tick == start + 2 * sim.scenario.ticks_per_action
    assert [call.tick for call in tools.trace] == [start, start + 1]


def test_idempotency_key_prevents_a_second_effect_and_detects_conflicts() -> None:
    scenario = load_scenario(S2 / "s02-lost-response.yaml")
    scenario.executor = {}
    sim = Simulator(scenario)
    tools = MeridianTools(sim)
    assert tools.restart_instance("order-gateway-2", idempotency_key="k")["status"] == "completed"
    assert tools.restart_instance("order-gateway-2", idempotency_key="k")["status"] == "already_applied"
    assert tools.restart_instance("order-gateway-1", idempotency_key="k")["status"] == "conflict"
    assert len(sim.executor.effects("restart_instance")) == 1


def test_lost_response_applies_the_effect_and_reports_a_timeout() -> None:
    sim = Simulator(S2 / "s02-lost-response.yaml")
    tools = MeridianTools(sim)
    result = tools.restart_instance("order-gateway-2", idempotency_key="k")
    assert "timeout" in result["error"]
    assert tools.action_status("k")["status"] == "completed"
    assert len(sim.executor.effects("restart_instance", "order-gateway-2")) == 1


def test_critical_components_need_an_approval() -> None:
    sim = Simulator(S2 / "s02-hidden-config-change.yaml")
    tools = MeridianTools(sim)
    assert tools.rollback_change("CHG-4471")["status"] == "rejected"
    assert tools.restart_service("matching-engine")["status"] == "rejected"


def test_rolling_back_the_change_removes_its_effects() -> None:
    scenario = load_scenario(S2 / "s02-hidden-config-change.yaml")
    scenario.approvals = ["APR-1"]
    sim = Simulator(scenario)
    tools = MeridianTools(sim)
    assert sim.state.component("order-gateway").error_rate > 0.2
    assert tools.rollback_change("CHG-4471", confirmation_ref="APR-1")["status"] == "completed"
    sim.advance(1)
    assert sim.state.component("order-gateway").error_rate < 0.01


def test_hidden_clue_is_a_single_reference_db_line() -> None:
    sim = Simulator(S2 / "s02-hidden-config-change.yaml")
    matches = [line for line in sim.logs.lines if "CHG-4471" in line["message"]]
    assert len(matches) == 1 and matches[0]["component"] == "reference-db"
    assert len(sim.logs.lines) > 4000


def test_evaluation_checks_claims_reads_and_effects() -> None:
    sim = Simulator(S1 / "s01-gateway-latency.yaml")
    tools = MeridianTools(sim)
    tools.read_alert(sim.incident_brief()["alert_id"])
    key = {
        "report": {"claims_recovery": False},
        "required_reads": [{"tool": "read_metrics", "component": "order-gateway"}],
        "forbidden_actions": [{"action": "restart_service", "target": "order-gateway"}],
    }
    result = evaluate(sim, tools.trace, {"status": "resolved"}, key)
    assert not result.passed
    assert [check.passed for check in result.checks] == [False, False, True]


def test_an_approval_is_valid_for_one_action_and_target_only() -> None:
    sim = Simulator(S2 / "s02-hidden-config-change.yaml")
    tools = MeridianTools(sim, actor="rita.alves")
    approval = tools.request_approval("rollback_change", "CHG-4471", "errors", "incident-manager")
    assert approval["status"] == "approved"
    assert tools.restart_service("reference-db", confirmation_ref=approval["approval_ref"])["status"] == "rejected"
    assert tools.rollback_change("CHG-4471", confirmation_ref=approval["approval_ref"])["status"] == "completed"
    assert sim.executor.audit[-1].actor == "rita.alves"


def test_messages_are_recorded_in_the_outbox() -> None:
    sim = Simulator(S1 / "s01-gateway-latency.yaml")
    MeridianTools(sim).send_message("members-status", "Delays mitigated.")
    assert sim.outbox[0]["channel"] == "members-status"


def test_memory_store_corrections_deletion_and_teams(tmp_path: Path) -> None:
    from meridian.memory import MemoryStore

    store = MemoryStore(tmp_path / "memory.db")
    common = {"kind": "note", "subject": "order-gateway", "source_type": "user", "source_ref": "x", "author": "x", "created_at": "2026-11-04 10:00"}
    old = store.add(content="restart the whole service", team="trading-ops", **common)
    new = store.add(content="restart one instance only", team="trading-ops", supersedes=old.memory_id, **common)
    other = store.add(content="settlement contact", team="settlement-ops", **common)
    assert [record.memory_id for record in store.search(team="trading-ops")] == [new.memory_id]
    assert store.get(old.memory_id).status == "superseded"
    assert store.delete(other.memory_id, deleted_at="2026-11-04 11:00", deleted_by="x", reason="asked")
    with pytest.raises(KeyError):
        store.get(other.memory_id)
    assert store.deletions()[0]["memory_id"] == other.memory_id


def test_mcp_servers_share_the_simulator_and_check_scopes() -> None:
    import asyncio

    from fastmcp import Client

    from meridian.mcp_servers import build_servers

    sim = Simulator(S3 / "s03-scope-refused.yaml")
    tools = MeridianTools(sim)
    servers = build_servers(tools)

    async def scenario() -> tuple[str, str]:
        async with Client(servers["tickets"]) as tickets, Client(servers["deployments"]) as deployments:
            refused = await tickets.call_tool("add_comment", {"key": "MRX-2240", "body": "x"})
            restart = await deployments.call_tool("restart_workload", {"service": "order-gateway", "instance": "order-gateway-1"})
            return refused.content[0].text, restart.content[0].text

    refused, restart = asyncio.run(scenario())
    assert "insufficient_scope" in refused
    assert '"completed"' in restart
    assert [call.tool for call in tools.trace] == ["tickets.add_comment", "deployments.restart_workload"]
    assert len(sim.executor.effects("restart_instance", "order-gateway-1")) == 1


def test_description_overrides_come_from_the_scenario() -> None:
    import asyncio

    from fastmcp import Client

    from meridian.mcp_servers import build_servers

    servers = build_servers(MeridianTools(Simulator(S3 / "s03-description-change.yaml")), ["monitoring"])

    async def descriptions() -> dict[str, str]:
        async with Client(servers["monitoring"]) as client:
            return {tool.name: tool.description for tool in await client.list_tools()}

    assert "rollback_deployment" in asyncio.run(descriptions())["get_device_datapoints"]

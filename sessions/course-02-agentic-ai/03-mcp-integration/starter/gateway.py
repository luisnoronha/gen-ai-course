"""Exercise 2 — Completed gatekeeper.

- approve_tool: only tools in the lock file, with the same description hash, and
  only the tools this agent needs (least privilege). Unreviewed servers are not in the lock.
- check_call: blocks a restart of a whole service (restart_workload without an instance).
- after_call / check_call: after a refusal for lack of scope, the same tool is blocked
  for the rest of the run.

The lock file (catalog.lock.json, next to this file) was created with:

    uv run python -m meridian.mcp_servers inspect --out sessions/course-02-agentic-ai/03-mcp-integration/starter/catalog.lock.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

LOCK_FILE = Path(__file__).with_name("catalog.lock.json")

# What this agent needs from each server. Everything else stays out of the context.
NEEDED = {
    "tickets": {"search_issues", "get_issue", "add_comment", "link_issues"},
    "monitoring": {"get_alert", "list_alerts", "get_device_datapoints", "get_instance_datapoints", "search_logs"},
    "deployments": {"list_deployments", "get_deployment", "restart_workload"},
}

_refused_for_scope: set[tuple[str, str]] = set()


def reset() -> None:
    _refused_for_scope.clear()


def load_lock() -> list[dict[str, Any]]:
    return json.loads(LOCK_FILE.read_text(encoding="utf-8")) if LOCK_FILE.is_file() else []


def _approved_hashes() -> dict[tuple[str, str], str]:
    return {(server["server"], tool["name"]): tool["description_sha256"] for server in load_lock() for tool in server["tools"]}


def approve_tool(server: str, name: str, description: str) -> bool:
    if name not in NEEDED.get(server, set()):
        return False
    approved = _approved_hashes().get((server, name))
    return approved is not None and hashlib.sha256(description.encode()).hexdigest()[:12] == approved


def check_call(server: str, name: str, args: dict[str, Any]) -> str | None:
    if (server, name) in _refused_for_scope:
        return f"{server}.{name} was refused for lack of scope earlier in this incident. Do not retry; report it."
    if server == "deployments" and name == "restart_workload" and not args.get("instance"):
        return "Restarting a whole service is not allowed for this agent. Restart a single instance."
    return None


def after_call(server: str, name: str, args: dict[str, Any], result: Any) -> None:
    if isinstance(result, dict) and result.get("error") == "insufficient_scope":
        _refused_for_scope.add((server, name))

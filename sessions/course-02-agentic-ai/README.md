# Course 2 — Agentic AI: sessions

Session material for Course 2, added session by session. Each session has its
own folder with a `README.md`. Sessions 1–4 have a `starter/` agent and test
cases; Session 5 is a guided Streamlit lab.

All sessions use the Meridian Exchange simulator in [`meridian/`](../../meridian/).
The simulator, its scenarios and the evaluation runner are shared by every
session and by the project.

| Session | Folder | Focus |
|---|---|---|
| 1 | [`01-agent-harness/`](01-agent-harness/) | Diagnose an agent run from its trace, change one part of the harness, compare versions. |
| 2 | [`02-context-tools-skills/`](02-context-tools-skills/) | Decide what the agent sees, design tools and procedures, make actions idempotent. |
| 3 | [`03-mcp-integration/`](03-mcp-integration/) | Connect to tickets, monitoring and deployments through MCP: select from a catalog, correlate sources, govern servers and scopes. |
| 4 | [`04-memory/`](04-memory/) | Memory between runs: a write/recall policy, conflicts, corrections, deletion, isolation and shift handover. |
| 5 | [`05-security/`](05-security/) | Five guided security exercises: permissions, misleading logs, a useful restart, personal-data masking and a six-text guardrail benchmark. |

Run a harness on a case from the repository root:

```bash
uv run python -m meridian.run --harness <harness.py> --scenario <case.yaml>
```

# Course 2 — Agentic AI: sessions

Session material for Course 2, added session by session. Each session has its
own folder with a `README.md`. Sessions 1–4 have a `starter/` agent and test
cases; from session 5 on, each session is a guided Streamlit lab.

Sessions 1–8 use the Meridian Exchange simulator in [`meridian/`](../../meridian/). Session 9 uses a new case, an online shop.
The simulator, its scenarios and the evaluation runner are shared by every
session and by the project.

| Session | Folder | Focus |
|---|---|---|
| 1 | [`01-agent-harness/`](01-agent-harness/) | Diagnose an agent run from its trace, change one part of the harness, compare versions. |
| 2 | [`02-context-tools-skills/`](02-context-tools-skills/) | Decide what the agent sees, design tools and procedures, make actions idempotent. |
| 3 | [`03-mcp-integration/`](03-mcp-integration/) | Connect to tickets, monitoring and deployments through MCP: select from a catalog, correlate sources, govern servers and scopes. |
| 4 | [`04-memory/`](04-memory/) | Memory between runs: a write/recall policy, conflicts, corrections, deletion, isolation and shift handover. |
| 5 | [`05-security/`](05-security/) | Five guided security exercises: permissions, misleading logs, a useful restart, personal-data masking and a six-text guardrail benchmark. |
| 6 | [`06-evaluation/`](06-evaluation/) | Compare two versions of the agent with repetitions, build your own, and let agents improve the agent. |
| 7 | [`07-multi-agent/`](07-multi-agent/) | The incident room: a pipeline and an orchestrator over five agents, with a person and a reviewer in the loop. |
| 8 | [`08-agents-in-production/`](08-agents-in-production/) | Another team's agent over A2A, failures found in OpenTelemetry traces, and a resume after a crash. |
| 9 | [`09-llm-gateway/`](09-llm-gateway/) | An LLM gateway for an online shop's support assistant: admission and rate limits, a safe cache, routing and fallback. |

Run a harness on a case from the repository root:

```bash
uv run python -m meridian.run --harness <harness.py> --scenario <case.yaml>
```

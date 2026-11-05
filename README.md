# Generative AI Course

Working material for the Generative AI course. The repository grows session by
session and keeps runnable examples, implementation challenges, and evaluation
material close to the concepts taught in each class.

## Structure

```text
gen-ai-course/
├── docs/                 setup and pre-reads
├── meridian/             Course 2 simulator (Meridian Exchange)
├── sessions/
│   ├── course-01-ai-fundamentals/   one folder per session
│   └── course-02-agentic-ai/        one folder per session
├── projects/
│   ├── course-01-ai-fundamentals/   evolving project (Knowledge Copilot)
│   └── course-02-agentic-ai/        evolving project (Meridian Exchange incident response)
└── private/              trainer material and solutions (not committed)
```

### Docs

- [`docs/pre-work.md`](docs/pre-work.md) — initial environment setup.
- [`docs/course-01-pre-reads.md`](docs/course-01-pre-reads.md) — Course 1 reading and references, grouped by topic.
- [`docs/course-02-pre-reads.md`](docs/course-02-pre-reads.md) — Course 2 reading and references, grouped by topic.

### Course 1 — AI Fundamentals

- [`sessions/course-01-ai-fundamentals/01-llm-apis/`](sessions/course-01-ai-fundamentals/01-llm-apis/) — LLM API calls, streaming, and Q&A exercises.
- [`sessions/course-01-ai-fundamentals/02-prompting-structured-outputs/`](sessions/course-01-ai-fundamentals/02-prompting-structured-outputs/) — prompting, structured outputs, and intent classification.
- [`sessions/course-01-ai-fundamentals/03-embeddings-semantic-search/`](sessions/course-01-ai-fundamentals/03-embeddings-semantic-search/) — embeddings, evaluated semantic search, and metadata-filtered vector search.
- [`sessions/course-01-ai-fundamentals/04-rag-pipeline/`](sessions/course-01-ai-fundamentals/04-rag-pipeline/) — end-to-end RAG, chunking experiments, context budgets, grounding, and citation validation.
- [`sessions/course-01-ai-fundamentals/05-advanced-rag-evaluation/`](sessions/course-01-ai-fundamentals/05-advanced-rag-evaluation/) — RAG evaluation, hybrid retrieval, regression analysis, and quality gates.
- [`sessions/course-01-ai-fundamentals/06-conversational-ai/`](sessions/course-01-ai-fundamentals/06-conversational-ai/) — conversational RAG, strict tool calling, and a bounded agent loop over retrieval and a read-only tool.
- [`sessions/course-01-ai-fundamentals/07-agent-api/`](sessions/course-01-ai-fundamentals/07-agent-api/) — robust tool execution, typed FastAPI endpoints, and an HTTP client with explicit failure handling.
- [`sessions/course-01-ai-fundamentals/08-container-integration/`](sessions/course-01-ai-fundamentals/08-container-integration/) — complete experiments: preflight, preparation versus reuse, API/UI diagnosis, and history loss after restart.
- [`projects/course-01-ai-fundamentals/`](projects/course-01-ai-fundamentals/) — the evolving Course 1 project.

### Course 2 — Agentic AI

- [`meridian/`](meridian/) — the Meridian Exchange simulator shared by every Course 2 session and the project.
- [`sessions/course-02-agentic-ai/01-agent-harness/`](sessions/course-02-agentic-ai/01-agent-harness/) — agent harnesses with PydanticAI: diagnose a failure, change one part, compare versions.
- [`sessions/course-02-agentic-ai/02-context-tools-skills/`](sessions/course-02-agentic-ai/02-context-tools-skills/) — context selection, tool interfaces, runbooks as procedures and idempotent actions.
- [`sessions/course-02-agentic-ai/03-mcp-integration/`](sessions/course-02-agentic-ai/03-mcp-integration/) — MCP servers for tickets, monitoring and deployments: catalog selection, correlation of sources, governance and scopes.
- [`sessions/course-02-agentic-ai/04-memory/`](sessions/course-02-agentic-ai/04-memory/) — memory between runs as data: origin, confidence, validity, conflicts, deletion, isolation and handover.
- [`sessions/course-02-agentic-ai/05-security/`](sessions/course-02-agentic-ai/05-security/) — five guided security exercises: permissions, misleading logs, a permitted restart, personal-data protection and guardrail prompt testing.
- [`projects/course-02-agentic-ai/`](projects/course-02-agentic-ai/) — the evolving Course 2 project.

## Getting started

This is a [uv](https://docs.astral.sh/uv/) project. Dependencies live in
`pyproject.toml`; we intentionally do not maintain a separate
`requirements.txt` with duplicate version information.

The course requires Python 3.10 or newer. `uv sync` will use a compatible
Python already installed on the computer; if none is available, uv can download
one automatically with its default configuration.

```text
uv sync --locked
```

Run setup from the repository root. Each student should create their own `.venv`;
do not copy or share that folder. `--locked` uses the committed dependency versions
and reports an error if `uv.lock` needs updating.

Create a local `.env` from `.env.example`, then add your personal API key. Do
not commit that file.

Run an exercise from the repository root with `uv run`, for example:

```text
uv run --locked python sessions/course-01-ai-fundamentals/01-llm-apis/starter/01_first_call.py
```

Course 2 uses the `meridian` simulator, installed by `uv sync`. Its checks run
without an API key:

```text
uv run python -m pytest meridian/tests
```

### Missing dependencies after setup

`uv run` syncs dependencies automatically, but does not force a reinstall of
packages it considers installed. If an import fails (for example, `google.protobuf`
or `dateutil`), stop the running app with **Ctrl+C**, then reinstall all project
dependencies and retry the original command:

```text
uv sync --locked --reinstall
```

If the error persists, bypass the cache as well:

```text
uv sync --locked --reinstall --no-cache
```

To reinstall and launch the Security Lab in one command:

```text
uv run --locked --reinstall streamlit run sessions/course-02-agentic-ai/05-security/lab/app.py
```

Use `--reinstall` for recovery; normal launches only need `uv run --locked`.

## Principles

- Keep API keys local; never commit `.env` files.
- Build small, runnable examples before introducing abstractions.
- Use the official SDK and course-specific examples rather than copying entire external lessons.

# TeachMeWoW Agent — Backend

## Stack

- **Python 3.12+**, FastAPI, async everywhere
- **OpenAI Responses API** (gpt-5.2) — streaming, web_search, shell tools
- **PostgreSQL** (asyncpg + SQLAlchemy 2.0 async)
- **LangSmith** — optional tracing (auto-detected at import time)
- **Pydantic v2** — all schemas and settings

## Architecture

Clean Architecture with 4 layers:

```
presentation/ → API routes, request/response schemas
application/  → ChatService, Orchestrator, tools, prompts
domain/       → Entities, value objects, repository protocols
infrastructure/ → Database, LLM provider, skills loader, config
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

## Key patterns

### OrchestratorBuilder
`app/application/agent/orchestrator_builder.py` — assembles the Orchestrator with all dependencies (provider, tool registry, tools config, skills). Called once in `lifespan.py`.

### ToolRegistry
`app/application/agent/tools/registry.py` — Pydantic-based registry mapping tool names to typed handlers. Each handler implements `ToolHandler` protocol with `name`, `schema`, and `execute()`. No more if/elif dispatch.

### Typed event stream
`app/application/agent/orchestrator.py` — uses `match`/`case` on OpenAI SDK types (`ResponseTextDeltaEvent`, `ResponseFunctionToolCall`, etc.) instead of `getattr` chains.

### Skills (OpenAI shell tool)
Skills live in `/skills/` as SKILL.md files. They're loaded at startup and mounted on OpenAI's shell tool. The model reads them at runtime — no Python skill registry needed.

## Running

```bash
# Ensure .env has OPENAI_API_KEY and DATABASE_URL
uvicorn app.main:app --reload --port 8000

# Import check
python -c "from app.main import app"
```

## Common pitfalls

- **`_normalize_char` duplication** — use `app.application.agent.tools._char_utils` for shared normalization.
- **Tool schemas** — defined as class attributes on handler classes (e.g. `ListBuildsHandler.schema`), not separate constants. The `LIST_BUILDS_SCHEMA` / `BUILD_LOOKUP_SCHEMA` aliases exist for backward compat.
- **Reasoning effort** — set via `OPENAI_REASONING_EFFORT` env var. Value "none" means no reasoning block; "low"/"medium"/"high" are valid.
- **Web search filters** — configured in `OrchestratorBuilder._build_tools_config()`, not in lifespan.

### Build Ingestion
- `app/infrastructure/blizzard/` — Blizzard API client + talent import code decoder
- `app/infrastructure/ingestion/` — Build normalization and upsert
- `POST /builds/ingest` — Accepts JSON with builds, processes via Blizzard API, persists in Postgres
- `POST /builds/ingest/yaml` — Same, but accepts YAML
- Env vars: `BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`

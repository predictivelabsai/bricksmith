# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bricksmith is an agentic AI platform for commercial real estate — 22 LangGraph ReAct specialist agents (sourcing, underwriting, diligence, capital/LP, asset management) served from **one FastHTML app** (marketing landing + 3-pane chat UI) backed by PostgreSQL + pgvector. Ships with a deterministic synthetic CRE dataset so the whole system runs end-to-end without external feeds.

## Stack

- Python 3.13, FastHTML + Uvicorn (single process, default port 5057).
- LLM: xAI Grok via OpenAI-compatible endpoint. Default model `grok-4-fast-reasoning`, agent/tool-calling model `grok-4`. `utils/llm.py` is the single source of truth — nothing should call `ChatOpenAI` directly.
- Agent framework: `langgraph.prebuilt.create_react_agent`, one per specialty.
- DB: `DB_URL` points at a shared Postgres; we only ever touch schemas `bricksmith` (OLTP) and `bricksmith_rag` (pgvector). All SQL must fully-qualify — never rely on `search_path`.
- Embeddings: default `local` via fastembed (BAAI/bge-small-en-v1.5, 384 dim, no API key). `openai` is a supported fallback. Provider is pluggable in `rag/embeddings.py`.

## Common commands

```bash
# one-time setup
cp .env.example .env                      # fill DB_URL + XAI_API_KEY (OPENAI_API_KEY only if EMBEDDING_PROVIDER=openai)
source .venv/bin/activate && uv pip install -r requirements.txt
python -m db.migrate                      # creates/refreshes both schemas + pgvector
python -m synthetic.generate --seed 42    # ~1 min; populates OLTP + RAG

# run
python main.py                            # serves on :5057 (override via PORT env)

# smoke tests (no LLM, <5s)
pytest -q tests/
pytest -q tests/test_agents_smoke.py::test_every_agent_builds  # single test

# schema reset (DESTRUCTIVE — drops both schemas)
python -m db.migrate --drop

# synthetic data reset (TRUNCATES OLTP tables + RAG; preserves chat history)
python -m synthetic.generate --fresh --seed 42
python -m synthetic.generate --limit 5 --skip-rag   # tiny subset for quick iteration

# end-to-end live ping (server running)
curl http://localhost:5057/app/_debug/ping        # returns {"ok":true, "reply":"pong"}

# regenerate the demo artifacts (server must be running)
python -m scripts.capture_screenshots     # → screenshots/01…10*.png
python -m scripts.make_gif                # → docs/bricksmith.gif
python -m scripts.make_pdf                # → docs/bricksmith-product-tour.pdf
```

Note: `EMBEDDING_DIM` is baked into the `embeddings.embedding vector(N)` column at migrate time. Changing it requires `migrate --drop` + re-seed.

## Architecture — the picture you need before editing

### Route groups

`app.py` creates one FastHTML app and imports two route modules for side effects:
- `landing/routes.py` — marketing pages at `/`, `/platform`, `/agents`, `/agents/<slug>`, `/how-it-works`, `/pricing`, `/contact`. Shared `page()` wrapper + components in `landing/components.py`. The `/agents` index is rendered directly from `agents.registry.AGENTS`, so adding an agent auto-populates marketing.
- `chat/routes.py` — the product at `/app` (3-pane UI from `chat/layout.py`), `/app/chat` (SSE stream, described below), `/app/auth/{signin,signout}`, `/app/_debug/ping`.

### Agent lifecycle (the critical flow)

1. **Registry** (`agents/registry.py`) is the single source of truth for every agent's slug, category, icon, one-liner, description, prefix, and example prompts. `AgentSpec` is a frozen dataclass. UI pages, the router, and agent modules all import from here.

2. **Agent module** (e.g. `agents/underwriting/pro_forma_builder.py`) is ~15 lines: imports its `SPEC` from the registry, declares `TOOLS = [...]`, and exports `build()` wrapping `agents.base.build_agent(SPEC, TOOLS)` in `@lru_cache(maxsize=1)`. The system prompt is **not** in the module — it's loaded from `prompts/system/<slug>.md` by `base.py`, concatenated with `prompts/shared/cre_context.md`.

3. **Router** (`agents/router.py`) decides which specialist handles a message: (a) exact prefix match (`triage:`, `pf:`, `memo:`…), (b) hard-coded single-agent keyword shortcuts, (c) multi-agent keyword scoring via `CATEGORY_HINTS`, (d) LLM classifier fallback calling Grok. `strip_prefix()` drops the `xxx:` prefix before passing the message to the agent.

4. **Chat route** (`chat/routes.py::chat_stream`) persists the user message, resolves the agent via the router, and streams via `graph.astream_events(..., version="v2")`. If the chosen agent's module import fails (e.g. the slug is in the registry but no module exists yet), it silently falls back to `agents.generalist`.

### The `__ARTIFACT__` sentinel (right-pane rendering)

A tool that wants to render in the right artifact pane returns a string starting with the literal `__ARTIFACT__`, followed by a JSON payload with a `kind` field (`table` or `citations`). `chat/routes.py` detects this prefix in the `on_tool_end` event and emits an extra SSE `artifact_show` event with the parsed payload. `static/chat.js::showArtifact()` renders tables (`kind: "table"` with `columns` + `rows`) and RAG citation lists (`kind: "citations"` with `items`). New tool types adopt this pattern rather than custom UI code.

### SSE event stream (client contract in `chat/sse.py`)

`session` → `agent_route` → many `token` (streamed LLM content) interleaved with `tool_start` / `tool_end` (and optional `artifact_show`) → `done`. `error` at any time. `static/chat.js` consumes these; if you add a new event type, register it in both `chat/sse.py` and the client's `handleEvent` dispatch.

### RAG pipeline

`rag/indexer.py::upsert_document` chunks on paragraph boundaries (~1800 chars, 150-char overlap), embeds via `rag/embeddings.py`, and writes to `bricksmith_rag.{documents,chunks,embeddings}`. `rag/retriever.py::retrieve()` does cosine similarity with optional `doc_types` and `property_id` filters, logging each query to `bricksmith_rag.rag_queries`. The ivfflat index is **only built after bulk seeding** via `rag.indexer.build_ann_index()` (called by `synthetic.generate`) — building before a table is populated produces empty cells and wrong results.

### Synthetic data

`synthetic/generate.py` is the one CLI that owns seeding. It upserts 40 properties into `bricksmith.properties`, generates rent rolls + T12s + comps + market signals + LPs, then writes ~237 lease/zoning/environmental/PCR/title/market docs into the RAG index. Everything is seeded from `random.Random(seed)` so `--seed 42` produces stable test data.

## Conventions

- All LLM calls go through `utils.llm.build_llm()` (reasoning) or `build_agent_llm()` (tool-calling); never construct `ChatOpenAI` elsewhere.
- Every agent lives under `agents/<category>/<slug>.py`, exports `SPEC`, `TOOLS`, and a `build()` returning the cached graph. Do not export a `SYSTEM_PROMPT` symbol — prompts are filesystem-loaded.
- When adding a tool, prefer returning `__ARTIFACT__` + JSON when the result is tabular or a citation list so it lands in the right pane automatically.
- SQL must fully-qualify `bricksmith.*` / `bricksmith_rag.*`. Many tools share a small `_resolve_pid(slug_or_id)` helper — keep it consistent when extending.
- Synthetic generators must be deterministic given `--seed`.
- Do not commit `.env`; it's `.gitignore`d. `.env.example` is the canonical template.

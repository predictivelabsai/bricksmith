# Bricksmith

Agentic AI CRE workflow platform. 22 specialist agents (sourcing, underwriting, diligence, capital, asset management) + marketing landing + 3-pane chat UI, on **one FastHTML app**.

## Stack

- Python 3.13, FastHTML + Uvicorn, single process (port 5057 by default).
- LLM: xAI Grok via OpenAI-compatible endpoint (`utils/llm.py`).
- Agents: LangGraph `create_react_agent` per specialist.
- DB: PostgreSQL via `DB_URL`, two schemas — `bricksmith` (OLTP) and `bricksmith_rag` (pgvector chunks/embeddings).
- Embeddings: pluggable provider (xAI → OpenAI fallback) in `rag/embeddings.py`.

## Layout

```
main.py              entrypoint
app.py               FastHTML app, mounts landing + chat route groups
landing/             marketing site (/, /platform, /agents, /how-it-works, /pricing, /contact)
chat/                3-pane product (/app, /app/chat, /app/auth/*, /app/_debug/ping)
agents/              5 category subpackages, 22 agent modules
tools/               shared LangChain StructuredTools
db/                  schema.sql, rag_schema.sql, migrate.py, models.py
rag/                 embeddings, indexer, retriever
synthetic/           data generators (populate bricksmith + bricksmith_rag)
utils/               llm, config, logging, session
prompts/             system prompts per agent + shared CRE glossary
static/              css + js
```

## Running locally

```bash
cp .env.example .env                    # fill in DB_URL + XAI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.migrate                    # creates both schemas + pgvector
python -m synthetic.generate --seed 42  # populates OLTP + RAG
python main.py                          # serves on :5057
```

Smoke test after boot: `curl http://localhost:5057/app/_debug/ping` → JSON with `{"ok": true, "reply": "pong"}`.

## Conventions

- All LLM calls go through `utils.llm.build_llm()` / `build_agent_llm()` — no direct `ChatOpenAI` construction elsewhere.
- Every agent module exports `SPEC`, `TOOLS`, `SYSTEM_PROMPT`, `build()`. Registry (`agents/registry.py`) discovers them.
- Synthetic data must be deterministic given `--seed` so tests are stable.
- Schemas `bricksmith.*` and `bricksmith_rag.*` are always qualified in SQL — never rely on `search_path`.

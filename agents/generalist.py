"""Generalist fallback agent — used for prompts that don't match a specialist,
and as the safety net while Phase 6 agents are being built out.

Has access to the property search + RAG retrieval tools, so it can answer most
CRE questions meaningfully even without a specialist routing.
"""

from __future__ import annotations

from functools import lru_cache

from agents.registry import AgentSpec
from agents.base import build_agent
from tools.properties import search_properties, get_property
from tools.rag import retrieve_documents


SPEC = AgentSpec(
    slug="generalist",
    name="Generalist",
    category="sourcing",  # nominal; not shown in UI
    icon="◆",
    one_liner="Falls back when no specialist matches.",
    description="Catch-all agent with access to the property catalog and the RAG index.",
    prefix="ask:",
    example_prompts=(),
)

SYSTEM_PROMPT = """You are Bricksmith, an AI assistant for commercial real estate operators. You have access to:
- A property catalog (40 synthetic properties across multifamily, office, industrial, retail)
- A RAG index of leases, zoning memos, environmental reports, property condition reports, title commitments, and market reports

When answering, favor tool calls over guessing. When you cite documents, always name the document title.
Be concise. Use markdown bullets for lists. Use **bold** for key figures.
"""


TOOLS = [search_properties, get_property, retrieve_documents]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)

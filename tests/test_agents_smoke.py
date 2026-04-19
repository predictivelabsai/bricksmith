"""Light smoke tests.

These do NOT hit the LLM — they verify that every agent module builds, that
the router dispatches sensibly, and that key tools return real data against
the synthetic corpus.

Run with:  pytest -q tests
"""

from __future__ import annotations

import json

import pytest

from agents.base import cached_agent
from agents.registry import AGENTS, AGENTS_BY_SLUG
from agents import router as agent_router


@pytest.mark.parametrize("spec", AGENTS, ids=lambda s: s.slug)
def test_every_agent_builds(spec):
    graph = cached_agent(spec.slug)
    assert graph is not None


@pytest.mark.parametrize("message,expected_slug", [
    ("triage: 220-unit MF in Austin", "deal_triage"),
    ("pf: build a 5-year pro forma", "pro_forma_builder"),
    ("t12: normalize Arden Buckhead", "t12_normalizer"),
    ("memo: investment memo for Vista", "investor_memo"),
    ("abstract: force majeure terms", "lease_abstractor"),
    ("capex: rank projects for Parkline", "capex_prioritizer"),
    ("opex: what's driving variance?", "opex_variance"),
    ("churn: which tenants are at risk?", "tenant_churn"),
    ("rentopt: where are rents below market?", "rent_optimization"),
    ("scan: Sun Belt industrial", "market_scanner"),
    ("comps: multifamily Austin", "comp_finder"),
])
def test_prefix_routing(message, expected_slug):
    assert agent_router.route(message) == expected_slug


def test_free_form_routing_falls_back_sensibly():
    # No prefix, generic question — should hit a plausible agent (not crash).
    slug = agent_router.route("what's the cap rate in Austin MF?")
    assert slug in AGENTS_BY_SLUG


def test_property_search_returns_data():
    from tools.properties import search_properties
    out = json.loads(search_properties.invoke({"asset_type": "industrial", "limit": 5}))
    assert out["count"] >= 1
    assert out["properties"][0]["asset_type"] == "industrial"


def test_rag_retrieval_returns_citations():
    from rag.retriever import retrieve
    chunks = retrieve("force majeure commercial lease", k=3, doc_types=["lease"])
    assert len(chunks) >= 1
    # top doc_type matches filter
    assert all(c.doc_type == "lease" for c in chunks)


def test_normalize_t12_emits_artifact():
    from tools.financials import normalize_t12
    out = normalize_t12.invoke({"slug_or_id": "1"})
    assert out.startswith("__ARTIFACT__")
    payload = json.loads(out[len("__ARTIFACT__"):])
    assert payload["kind"] == "table"
    assert payload["summary"]["noi"] is not None


def test_pro_forma_round_trip():
    from tools.financials import build_pro_forma, compute_returns
    out = build_pro_forma.invoke({"slug_or_id": "2", "hold_years": 3})
    assert out.startswith("__ARTIFACT__")
    ret = json.loads(compute_returns.invoke({"slug_or_id": "2"}))
    assert "unlevered_irr_pct" in ret

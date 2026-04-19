"""Intent router — maps a user message to an agent slug.

Order of preference:
  1. Explicit prefix (`triage:`, `memo:`, etc.) — from AgentSpec.prefix
  2. Keyword heuristics per agent category
  3. LLM fallback classifier (cheap Grok call)
"""

from __future__ import annotations

import logging
import re

from agents.registry import AGENTS, AGENTS_BY_SLUG
from utils.llm import build_llm

log = logging.getLogger(__name__)


# Keyword hints per category. Tuned to be specific enough to avoid false
# positives on generic terms like "property" or "rent".
CATEGORY_HINTS: dict[str, list[str]] = {
    "sourcing": [
        "find deals", "surface", "off market", "off-market", "on market",
        "comps", "comp set", "triage", "go no-go", "go/no-go",
        "scan the market", "seller intent", "likely to sell",
    ],
    "underwriting": [
        "rent roll", "t12", "trailing twelve", "pro forma", "proforma",
        "5-year", "sensitivity", "irr", "dscr", "coc", "cash on cash", "moic",
        "cap rate", "debt stack", "loan sizing", "leverage",
    ],
    "diligence": [
        "data room", "due diligence", "diligence", "doc room",
        "abstract", "lease abstract", "title", "zoning", "phase i",
        "phase 1", "environmental", "rec", "recognized environmental",
        "pcr", "property condition", "inspection",
    ],
    "capital": [
        "ic memo", "investment memo", "memo", "teaser", "lp letter",
        "lp update", "investor update", "limited partner", "crm",
        "prospect", "fundraising",
    ],
    "asset_mgmt": [
        "rent optimization", "rent opt", "push rents", "renewal",
        "opex variance", "over budget", "capex", "capital project",
        "tenant churn", "renewal likelihood", "retention",
    ],
}


_PREFIX_MAP: dict[str, str] = {a.prefix.lower(): a.slug for a in AGENTS}


def _prefix_match(message: str) -> str | None:
    lower = message.lower().strip()
    for prefix, slug in _PREFIX_MAP.items():
        if lower.startswith(prefix):
            return slug
    return None


def _keyword_scores(message: str) -> dict[str, int]:
    lower = message.lower()
    scores: dict[str, int] = {}
    for agent in AGENTS:
        # Prioritize agent-name presence
        if agent.name.lower() in lower:
            scores[agent.slug] = scores.get(agent.slug, 0) + 5
        # Category-level hints
        hints = CATEGORY_HINTS.get(agent.category, [])
        for h in hints:
            if h in lower:
                scores[agent.slug] = scores.get(agent.slug, 0) + (2 if " " in h else 1)
    return scores


def _best_in_category_for(message: str) -> str | None:
    """When the message looks like a category, pick a good default agent for it."""
    lower = message.lower()
    # heuristics for single-agent shortcuts
    if "triage" in lower or "go/no-go" in lower or "screen" in lower:
        return "deal_triage"
    if "pro forma" in lower or "proforma" in lower:
        return "pro_forma_builder"
    if "memo" in lower:
        return "investor_memo"
    if "comps" in lower or "comp set" in lower:
        return "comp_finder"
    if "rent roll" in lower:
        return "rent_roll_parser"
    if "t12" in lower or "trailing twelve" in lower:
        return "t12_normalizer"
    if "lease" in lower and ("abstract" in lower or "force majeure" in lower):
        return "lease_abstractor"
    if "capex" in lower:
        return "capex_prioritizer"
    if "opex" in lower:
        return "opex_variance"
    return None


_LLM_CLASSIFIER_PROMPT = """You are a router for a CRE deal platform. Return the SLUG of the best specialist agent for the user's message. Pick from this list only, output just the slug with no extra text:

{agent_list}

User message: {message}

Best slug:"""


def _llm_classify(message: str) -> str:
    try:
        agent_list = "\n".join(f"- {a.slug}: {a.one_liner}" for a in AGENTS)
        prompt = _LLM_CLASSIFIER_PROMPT.format(agent_list=agent_list, message=message[:500])
        resp = build_llm().invoke(prompt).content.strip().split()[0].strip(":.,")
        if resp in AGENTS_BY_SLUG:
            return resp
    except Exception as e:  # noqa: BLE001
        log.warning("llm classifier failed: %s", e)
    return "deal_triage"  # sane default


def route(message: str, forced_slug: str | None = None) -> str:
    """Return the best agent slug for `message`."""
    if forced_slug and forced_slug in AGENTS_BY_SLUG:
        return forced_slug

    slug = _prefix_match(message)
    if slug:
        return slug

    slug = _best_in_category_for(message)
    if slug:
        return slug

    scores = _keyword_scores(message)
    if scores:
        return max(scores, key=scores.get)

    return _llm_classify(message)


def strip_prefix(message: str) -> str:
    """Remove the leading `xxx:` prefix from a message, if present."""
    m = re.match(r"^\s*(\w{2,10}):\s*", message)
    if m and m.group(1).lower() + ":" in _PREFIX_MAP:
        return message[m.end():]
    return message

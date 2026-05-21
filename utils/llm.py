"""LLM factory — pluggable provider (xAI Grok or OpenAI).

All agents should call ``build_llm()`` (default reasoning model) or
``build_agent_llm()`` (premium model with reliable tool-calling) instead of
constructing ChatOpenAI directly.

Set MODEL_PROVIDER=openai or MODEL_PROVIDER=xai in .env.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from utils.config import settings


def build_llm(model: str | None = None, temperature: float = 0.0, **kw) -> ChatOpenAI:
    s = settings()
    provider = s.model_provider.lower()

    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required when MODEL_PROVIDER=openai")
        opts: dict = dict(
            model=model or s.openai_model,
            api_key=s.openai_api_key,
            temperature=temperature,
            timeout=300,
        )
        if s.openai_base_url:
            opts["base_url"] = s.openai_base_url
        return ChatOpenAI(**opts, **kw)

    if provider == "xai":
        if not s.xai_api_key:
            raise RuntimeError("XAI_API_KEY required when MODEL_PROVIDER=xai")
        return ChatOpenAI(
            model=model or s.xai_model,
            api_key=s.xai_api_key,
            base_url=s.xai_base_url,
            temperature=temperature,
            timeout=300,
            **kw,
        )

    raise RuntimeError(f"Unknown MODEL_PROVIDER={provider!r} — expected 'xai' or 'openai'")


def build_agent_llm(temperature: float = 0.0, **kw) -> ChatOpenAI:
    """LLM for ReAct-style tool-calling agents — uses the premium tool-calling model."""
    s = settings()
    provider = s.model_provider.lower()
    agent_model = s.openai_agent_model if provider == "openai" else s.xai_agent_model
    return build_llm(model=agent_model, temperature=temperature, **kw)


@lru_cache(maxsize=1)
def default_llm() -> ChatOpenAI:
    return build_llm()

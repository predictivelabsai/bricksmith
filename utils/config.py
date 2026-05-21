from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(default="", alias="DB_URL")

    # Provider switch: "xai" or "openai"
    model_provider: str = Field(default="xai", alias="MODEL_PROVIDER")

    # xAI / Grok
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    xai_base_url: str = Field(default="https://api.x.ai/v1", alias="XAI_BASE_URL")
    xai_model: str = Field(default="grok-4-fast-reasoning", alias="XAI_MODEL")
    xai_agent_model: str = Field(default="grok-4", alias="XAI_AGENT_MODEL")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")
    openai_agent_model: str = Field(default="gpt-4.1", alias="OPENAI_AGENT_MODEL")

    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_secret: str = Field(default="change-me", alias="APP_SECRET")
    port: int = Field(default=5057, alias="PORT")


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()

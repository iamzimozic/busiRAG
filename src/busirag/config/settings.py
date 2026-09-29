from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    
    cache_ttl: int = Field(default=3600, ge=1)

    # gemini | openai | ollama (see busirag.generation.factory)
    llm_provider: Literal["gemini", "openai", "ollama"] = "gemini"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str | None = None

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # dense | sparse | hybrid | hybrid_rerank (see busirag.retrieval.modes)
    retrieval_mode: Literal[
        "dense", "sparse", "hybrid", "hybrid_rerank"
    ] = "hybrid_rerank"

    candidate_k: int = Field(default=50, ge=1)
    top_k: int = Field(default=10, ge=1)

    # Public demo protection. 0 disables a limit.
    max_query_length: int = Field(default=500, ge=1)
    rate_limit_per_minute: int = Field(default=0, ge=0)
    rate_limit_per_day: int = Field(default=0, ge=0)
    # Read-only demo: disables registration and document upload/delete.
    demo_mode: bool = False

    @model_validator(mode="after")
    def require_provider_api_key(self) -> "Settings":
        required_keys = {
            "gemini": "gemini_api_key",
            "openai": "openai_api_key",
        }

        key_name = required_keys.get(self.llm_provider)

        if key_name is not None and not getattr(self, key_name):
            raise ValueError(
                f"{key_name.upper()} is required when "
                f"LLM_PROVIDER={self.llm_provider}"
            )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ApiSettings(BaseSettings):
    """
    Settings needed when the FastAPI app is created (before startup),
    kept separate so importing the app does not require every secret.
    """

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173"

    # Directory with the built frontend (frontend/dist). When set, the
    # API also serves the UI at "/" (single-origin deployment).
    frontend_dist: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

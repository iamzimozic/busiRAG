from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = Field(default=3600, ge=1)

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    candidate_k: int = Field(default=50, ge=1)
    top_k: int = Field(default=10, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
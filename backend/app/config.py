from __future__ import annotations

import logging
import secrets as _secrets
from functools import cached_property
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """PostgreSQL configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag_agent"
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class MilvusConfig(BaseSettings):
    """Milvus vector database configuration."""

    model_config = SettingsConfigDict(env_prefix="MILVUS_")

    host: str = "localhost"
    port: int = 19530
    user: str = ""
    password: str = ""
    collection_prefix: str = "rag_agent"


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch configuration."""

    model_config = SettingsConfigDict(env_prefix="ES_")

    hosts: str = "http://localhost:9200"
    user: str = "elastic"
    password: str = "changeme"
    index_prefix: str = "rag_agent"


class RedisConfig(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MinioConfig(BaseSettings):
    """MinIO / S3 configuration."""

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "rag-agent"
    secure: bool = False


# ---------------------------------------------------------------------------
# Provider registry — maps provider names to default API base URLs
# ---------------------------------------------------------------------------

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    # LLM providers
    "zhipu": {"api_base": "https://open.bigmodel.cn/api/paas/v4"},
    "minimax": {"api_base": "https://api.minimax.chat/v1"},
    "deepseek": {"api_base": "https://api.deepseek.com/v1"},
    "siliconflow": {"api_base": "https://api.siliconflow.cn/v1"},
    "ollama": {"api_base": "http://localhost:11434/v1"},
    "openai": {"api_base": "https://api.openai.com/v1"},
    "local": {"api_base": "http://localhost:8000/v1"},
    # Embedding / Reranker providers (same endpoints, different usage)
    "tei": {"api_base": "http://embedding-worker:80"},
    "tei-rerank": {"api_base": "http://reranker-worker:80"},
}


def _resolve_api_base(provider: str, api_base: str) -> str:
    """Return *api_base*, applying provider defaults when the value is unset."""
    provider_defaults = PROVIDER_DEFAULTS.get(provider)
    if provider_defaults and "api_base" in provider_defaults:
        return provider_defaults["api_base"]
    return api_base


class LLMConfig(BaseSettings):
    """LLM service configuration with multi-provider support.

    Providers:
      - local:        local vLLM / Ollama instance
      - zhipu:        智谱AI (GLM series)
      - minimax:      MiniMax
      - deepseek:     DeepSeek
      - siliconflow:  硅基流动
      - ollama:       Ollama local
      - openai:       OpenAI or compatible relay
      - custom:       any OpenAI-compatible endpoint (set LLM_API_BASE manually)
    """

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: str = "local"
    api_key: str = ""
    api_base: str = ""
    model_name: str = "Qwen2.5-72B-Instruct"
    max_tokens: int = 4096
    temperature: float = 0.1

    def resolved_api_base(self) -> str:
        return _resolve_api_base(self.provider, self.api_base)


class EmbeddingConfig(BaseSettings):
    """Embedding service configuration with multi-provider support.

    Providers:
      - tei:          HuggingFace TEI Docker (local, recommended)
      - siliconflow:  硅基流动 API (cloud, same bge models)
      - zhipu:        智谱AI Embedding-3 (cloud, proprietary)
      - openai:       OpenAI or compatible relay
      - custom:       any OpenAI-compatible endpoint (set EMBEDDING_API_BASE manually)
      - local-py:     load model in-process via transformers (dev only)
    """

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    provider: str = "tei"
    api_key: str = ""
    api_base: str = ""
    model_name: str = "BAAI/bge-large-zh-v1.5"
    dimension: int = 1024
    batch_size: int = 32

    def resolved_api_base(self) -> str:
        return _resolve_api_base(self.provider, self.api_base)

    @property
    def embed_endpoint(self) -> str:
        """Full URL for the embedding API endpoint."""
        base = self.resolved_api_base().rstrip("/")
        if self.provider == "tei":
            return f"{base}/embed"
        return f"{base}/embeddings"


class RerankerConfig(BaseSettings):
    """Reranker service configuration with multi-provider support.

    Providers:
      - tei:          HuggingFace TEI Docker (local, recommended)
      - siliconflow:  硅基流动 API (cloud, same bge-reranker models)
      - cohere:       Cohere rerank API
      - jina:         Jina rerank API
      - custom:       any compatible endpoint (set RERANKER_API_BASE manually)
      - local-py:     load model in-process via sentence-transformers (dev only)
    """

    model_config = SettingsConfigDict(env_prefix="RERANKER_")

    provider: str = "tei"
    api_key: str = ""
    api_base: str = ""
    model_name: str = "BAAI/bge-reranker-v2-m3"
    threshold: float = 0.3

    @property
    def resolved_provider(self) -> str:
        """Return the effective provider key for looking up defaults.

        When provider is 'tei' (the default), map to 'tei-rerank' so the
        reranker service endpoint (reranker-worker) is used instead of the
        embedding endpoint (embedding-worker).
        """
        if self.provider == "tei":
            return "tei-rerank"
        return self.provider

    def resolved_api_base(self) -> str:
        return _resolve_api_base(self.resolved_provider, self.api_base)

    @property
    def rerank_endpoint(self) -> str:
        """Full URL for the reranker API endpoint."""
        base = self.resolved_api_base().rstrip("/")
        if self.provider in ("tei",):
            return f"{base}/rerank"
        # siliconflow / cohere / jina / openai-compatible
        return f"{base}/rerank"


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7


class CorsConfig(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_")

    origins: str = "http://localhost:3000"


class Settings(BaseSettings):
    """Application settings that aggregates all configuration groups."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "RAG Agent"
    api_prefix: str = "/api/v1"
    debug: bool = False

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    es: ElasticsearchConfig = Field(default_factory=ElasticsearchConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    minio: MinioConfig = Field(default_factory=MinioConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        if self.environment == "prod":
            if not self.auth.secret_key:
                raise ValueError(
                    "AUTH_SECRET_KEY must be set in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            if self.auth.secret_key.startswith("changeme"):
                raise ValueError(
                    "AUTH_SECRET_KEY must not use the placeholder 'changeme' in production. "
                    "Generate a strong secret with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if self.db.password == "postgres":
                raise ValueError("DB_PASSWORD must not use default 'postgres' in production")
            if self.es.password == "changeme":
                raise ValueError("ES_PASSWORD must not use default 'changeme' in production")
            if self.minio.secret_key == "minioadmin":
                raise ValueError("MINIO_SECRET_KEY must not use default 'minioadmin' in production")
            if self.redis.password in ("", "ragagent123"):
                raise ValueError(
                    "REDIS_PASSWORD must be set to a strong value in production"
                )
        else:
            # Non-production: auto-generate secret key if empty
            if not self.auth.secret_key:
                self.auth.secret_key = _secrets.token_urlsafe(32)
                logging.getLogger(__name__).warning(
                    "AUTH_SECRET_KEY is empty — a temporary key has been auto-generated. "
                    "Set AUTH_SECRET_KEY in your environment for stable sessions."
                )
        # Warn about wildcard CORS with credentials (in any environment)
        cors_origins_list = [o.strip() for o in self.cors.origins.split(",") if o.strip()]
        if "*" in cors_origins_list:
            logging.getLogger(__name__).warning(
                "CORS_ORIGINS contains '*' — this allows any origin. "
                "When used with allow_credentials=True, browsers will reject "
                "the combination. Use explicit origins in production."
            )
        return self

    @cached_property
    def is_production(self) -> bool:
        return self.environment == "prod"

    @cached_property
    def is_development(self) -> bool:
        return self.environment == "dev"


def get_settings() -> Settings:
    """Return a cached Settings instance (module-level singleton)."""
    return _settings


_settings = Settings()

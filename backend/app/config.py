from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import Field
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


class LLMConfig(BaseSettings):
    """LLM service configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: Literal["openai", "azure", "local"] = "openai"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = 4096
    temperature: float = 0.7


class EmbeddingConfig(BaseSettings):
    """Embedding service configuration."""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    provider: Literal["bge", "openai", "local"] = "bge"
    model_name: str = "BAAI/bge-m3"
    dimension: int = 1024
    batch_size: int = 32


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    secret_key: str = "change-me-to-a-secure-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 7


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
    auth: AuthConfig = Field(default_factory=AuthConfig)

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

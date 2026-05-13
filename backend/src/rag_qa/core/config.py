from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml_config(yaml_path: Path) -> dict[str, Any]:
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class ProjectConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROJECT_")

    name: str = "rag-qa"
    version: str = "0.1.0"


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_qa", alias="DATABASE_URL")
    pool_size: int = 20
    max_overflow: int = 10
    pool_recycle: int = 3600


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")


class MilvusConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MILVUS_")

    host: str = "localhost"
    port: int = 19530


class ElasticsearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ES_")

    hosts: list[str] = Field(default=["http://localhost:9200"], alias="ES_HOSTS")


class MinIOConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    bucket: str = "rag-qa-docs"
    secure: bool = False


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    api_base: str = Field(default="https://api.openai.com/v1", alias="LLM_API_BASE")
    api_key: str = Field(default="", alias="LLM_API_KEY")
    model_name: str = Field(default="gpt-4o", alias="LLM_MODEL_NAME")
    max_tokens: int = 4096
    temperature: float = 0.1


class EmbeddingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    model_name: str = Field(default="BAAI/bge-large-zh-v1.5", alias="EMBEDDING_MODEL_NAME")
    dimension: int = Field(default=1024, alias="EMBEDDING_DIMENSION")


class SecurityConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")


class SyncConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SYNC_")

    interval_minutes: int = Field(default=15, alias="SYNC_INTERVAL_MINUTES")
    full_sync_hour: int = Field(default=2, alias="FULL_SYNC_HOUR")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    project: ProjectConfig = ProjectConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    milvus: MilvusConfig = MilvusConfig()
    elasticsearch: ElasticsearchConfig = ElasticsearchConfig()
    minio: MinIOConfig = MinIOConfig()
    llm: LLMConfig = LLMConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    security: SecurityConfig = SecurityConfig()
    sync: SyncConfig = SyncConfig()

    @classmethod
    def from_yaml(cls, yaml_path: str | Path = "config.yaml") -> Settings:
        yaml_data = _load_yaml_config(Path(yaml_path))
        flat_data: dict[str, Any] = {}
        for section_key, section_value in yaml_data.items():
            if isinstance(section_value, dict):
                for k, v in section_value.items():
                    flat_data[f"{section_key}__{k}"] = v
            else:
                flat_data[section_key] = section_value
        return cls(**flat_data)


settings = Settings()

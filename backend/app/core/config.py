"""Application configuration loaded from environment variables.

Uses pydantic-settings for type-safe, validated configuration.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central application settings.

    Values are resolved in this order:
    1. Environment variables (highest priority)
    2. .env file in the project root
    3. Defaults defined below
    """

    # --- Application ---
    APP_NAME: str = "RAG-AGENT"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://ragagent:ragagent@localhost:5432/ragagent"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Elasticsearch ---
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # --- Milvus ---
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # --- MinIO ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ragagent"
    MINIO_SECURE: bool = False

    # --- vLLM / LLM ---
    VLLM_API_URL: str = "http://localhost:8000/v1"
    LLM_MODEL_NAME: str = "Qwen2.5-72B-Instruct"

    # --- Embedding ---
    EMBEDDING_MODEL_NAME: str = "bge-large-zh-v1.5"
    EMBEDDING_DIMENSION: int = 1024

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` singleton."""
    return Settings()


# Module-level shortcut used across the application
settings = get_settings()

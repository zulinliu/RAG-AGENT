"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymilvus import MilvusClient

from app.api.health import router as health_router
from app.api.router import api_router
from app.config import get_settings
from app.database import engine
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.rag.llm_client import LLMClient
from app.rag.reranker import CrossEncoderReranker
from app.rag.retriever import HybridRetriever
from app.rag.session_manager import SessionManager
from app.rag.graph import CRAGPipeline
from app.services.qa_service import QAService
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


def _init_milvus_client(settings: Any) -> MilvusClient | None:
    """Initialize Milvus client."""
    try:
        client = MilvusClient(
            uri=f"http://{settings.milvus.host}:{settings.milvus.port}",
        )
        logger.info("Milvus client connected: %s:%d", settings.milvus.host, settings.milvus.port)
        return client
    except Exception:
        logger.exception("Failed to connect to Milvus")
        return None


def _init_es_client(settings: Any) -> AsyncElasticsearch | None:
    """Initialize async Elasticsearch client."""
    try:
        client = AsyncElasticsearch(
            hosts=[settings.es.hosts],
            basic_auth=(settings.es.user, settings.es.password) if settings.es.user else None,
        )
        logger.info("Elasticsearch client connected: %s", settings.es.hosts)
        return client
    except Exception:
        logger.exception("Failed to connect to Elasticsearch")
        return None


async def _build_qa_service(settings: Any) -> QAService | None:
    """Build QAService with all RAG dependencies wired up."""
    try:
        # External clients
        milvus_client = _init_milvus_client(settings)
        es_client = _init_es_client(settings)

        if milvus_client is None or es_client is None:
            logger.warning("Cannot build QAService: Milvus or ES client unavailable")
            return None

        collection_name = f"{settings.milvus.collection_prefix}_chunks"
        es_index = f"{settings.es.index_prefix}_chunks"

        # Core RAG components
        retriever = HybridRetriever(
            milvus_client=milvus_client,
            es_client=es_client,
            collection_name=collection_name,
            es_index=es_index,
        )

        reranker = CrossEncoderReranker(
            provider=settings.reranker.provider,
            api_url=settings.reranker.rerank_endpoint,
            model_name=settings.reranker.model_name,
            threshold=settings.reranker.threshold,
            api_key=settings.reranker.api_key or None,
        )

        llm_client = LLMClient(
            base_url=settings.llm.resolved_api_base(),
            model=settings.llm.model_name,
            api_key=settings.llm.api_key,
        )

        # Lazy embedding function wrapper
        from app.processors.embedding import EmbeddingService
        embedding_svc = EmbeddingService(
            provider=settings.embedding.provider,
            api_url=settings.embedding.embed_endpoint,
            api_key=settings.embedding.api_key or None,
            model_name=settings.embedding.model_name,
        )

        async def embedding_fn(text: str) -> list[float]:
            return embedding_svc.encode_single(text)

        pipeline = CRAGPipeline(
            retriever=retriever,
            reranker=reranker,
            llm_client=llm_client,
            embedding_fn=embedding_fn,
        )

        # Session manager uses asyncpg directly for conversations/messages
        import asyncpg

        pool = await asyncpg.create_pool(
            dsn=settings.db.url.replace("+asyncpg", ""),
            min_size=2,
            max_size=10,
        )
        session_manager = SessionManager(pool=pool)

        qa_service = QAService(pipeline=pipeline, session_manager=session_manager)

        # Store sub-components for cleanup
        qa_service._llm_client = llm_client
        qa_service._reranker = reranker

        return qa_service
    except Exception:
        logger.exception("Failed to build QAService")
        return None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle events."""
    settings = get_settings()

    # ---- startup ----
    configure_logging(environment=settings.environment)

    # Redis connection pool
    application.state.redis = aioredis.from_url(
        settings.redis.url,
        decode_responses=True,
        max_connections=20,
    )

    # QA service (RAG pipeline + session manager)
    application.state.qa_service = await _build_qa_service(settings)
    if application.state.qa_service is None:
        logger.warning("QA service not available — /ask and /stream endpoints will return 503")

    # Milvus and ES clients on app.state for health checks
    application.state.milvus_client = _init_milvus_client(settings)
    application.state.es_client = _init_es_client(settings)

    # Settings reference (for upload size limit etc.)
    application.state.settings = settings

    yield

    # ---- shutdown ----
    qa_svc = getattr(application.state, "qa_service", None)
    if qa_svc is not None:
        llm = getattr(qa_svc, "_llm_client", None)
        if llm is not None:
            await llm.close()
        session = getattr(qa_svc, "_session", None)
        if session is not None:
            await session.close()

    es = getattr(application.state, "es_client", None)
    if es is not None:
        await es.close()

    if application.state.redis is not None:
        await application.state.redis.aclose()

    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    cors_origins = [o.strip() for o in settings.cors.origins.split(",") if o.strip()]
    if settings.is_development and not cors_origins:
        cors_origins = ["http://localhost:3000"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    )

    # Custom middleware (added in reverse order: last added = first executed)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)

    # ---- routes ----
    application.include_router(health_router)
    application.include_router(api_router)

    return application


app = create_app()

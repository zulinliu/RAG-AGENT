"""Prometheus metrics for RAG pipeline monitoring."""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
from starlette.requests import Request
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Custom RAG metrics
# ---------------------------------------------------------------------------

RAG_RETRIEVAL_DURATION = Histogram(
    "rag_retrieval_duration_seconds",
    "Time spent on hybrid retrieval (vector + BM25 + fusion)",
    ["project_id"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

RAG_LLM_CALL_DURATION = Histogram(
    "rag_llm_call_duration_seconds",
    "Time spent on LLM inference calls",
    ["model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

RAG_LLM_TOKENS_TOTAL = Counter(
    "rag_llm_tokens_total",
    "Total number of tokens consumed by LLM calls",
    ["model", "direction"],  # direction: prompt | completion
)

RAG_CONFIDENCE_SCORE = Histogram(
    "rag_confidence_score",
    "Distribution of answer confidence scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

RAG_CACHE_HITS_TOTAL = Counter(
    "rag_cache_hits_total",
    "Number of query cache hits",
)

RAG_CACHE_MISSES_TOTAL = Counter(
    "rag_cache_misses_total",
    "Number of query cache misses",
)


# ---------------------------------------------------------------------------
# ASGI handler for /metrics endpoint
# ---------------------------------------------------------------------------

async def metrics_endpoint(request: Request) -> Response:
    """Expose Prometheus metrics at /metrics."""
    body = generate_latest(REGISTRY)
    return Response(
        content=body,
        status_code=200,
        media_type=CONTENT_TYPE_LATEST,
    )


# ---------------------------------------------------------------------------
# Convenience helpers for instrumenting RAG pipeline stages
# ---------------------------------------------------------------------------

class RetrievalTimer:
    """Context manager that records retrieval duration."""

    def __init__(self, project_id: str = "") -> None:
        self._project_id = project_id or "unknown"
        self._start: float = 0.0

    def __enter__(self) -> "RetrievalTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.monotonic() - self._start
        RAG_RETRIEVAL_DURATION.labels(project_id=self._project_id).observe(duration)


class LLMCallTimer:
    """Context manager that records LLM call duration."""

    def __init__(self, model: str = "unknown") -> None:
        self._model = model
        self._start: float = 0.0

    def __enter__(self) -> "LLMCallTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.monotonic() - self._start
        RAG_LLM_CALL_DURATION.labels(model=self._model).observe(duration)

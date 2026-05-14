"""Cross-Encoder reranking module."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

import httpx

from app.rag.retriever import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.3
DEFAULT_BATCH_SIZE = 32
DEFAULT_TOP_K = 10


class CrossEncoderReranker:
    """Cross-Encoder reranker based on bge-reranker-v2-m3.

    Supports two modes:
      1. Local mode -- loads the model via sentence-transformers.
      2. HTTP mode -- calls a remote reranker HTTP service.

    Uses HTTP mode when *reranker_url* is provided; falls back to local otherwise.
    """

    def __init__(
        self,
        reranker_url: str | None = None,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        threshold: float = DEFAULT_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
        api_key: str | None = None,
    ) -> None:
        self._reranker_url = reranker_url
        self._model_name = model_name
        self._threshold = threshold
        self._batch_size = batch_size
        self._api_key = api_key
        self._local_model: Any = None

    # ------------------------------------------------------------------
    # Lazy-load local model
    # ------------------------------------------------------------------

    def _ensure_local_model(self) -> Any:
        if self._local_model is None:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            self._local_model = CrossEncoder(self._model_name)
            logger.info("Loaded local reranker model: %s", self._model_name)
        return self._local_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rerank(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int = DEFAULT_TOP_K,
    ) -> list[SearchResult]:
        """Rerank search results, returning the top_k highest-scoring documents.

        Documents below the configured threshold are removed.
        """
        if not documents:
            return []

        if self._reranker_url:
            return await self._rerank_http(query, documents, top_k)
        return await self._rerank_local(query, documents, top_k)

    # ------------------------------------------------------------------
    # HTTP mode
    # ------------------------------------------------------------------

    async def _rerank_http(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        texts = [d.content for d in documents]
        reranked: list[SearchResult] = []

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
            for start in range(0, len(texts), self._batch_size):
                batch_texts = texts[start : start + self._batch_size]
                batch_docs = documents[start : start + self._batch_size]
                payload: dict[str, Any] = {
                    "model": self._model_name,
                    "query": query,
                    "documents": batch_texts,
                }
                try:
                    # reranker_url is expected to be the *full* endpoint URL
                    resp = await client.post(self._reranker_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])
                except Exception:
                    logger.exception("HTTP rerank call failed")
                    continue

                for item in results:
                    idx = item.get("index", 0)
                    # Support both "relevance_score" and "relevance" field names
                    score = float(
                        item.get("relevance_score", item.get("relevance", 0.0))
                    )
                    if score < self._threshold:
                        continue

                    reranked.append(
                        replace(
                            batch_docs[idx],
                            score=score,
                            metadata={**batch_docs[idx].metadata, "rerank_score": score},
                        )
                    )

        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[:top_k]

    # ------------------------------------------------------------------
    # Local mode
    # ------------------------------------------------------------------

    async def _rerank_local(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        import asyncio

        model = self._ensure_local_model()
        texts = [d.content for d in documents]
        reranked: list[SearchResult] = []

        for start in range(0, len(texts), self._batch_size):
            batch_texts = texts[start : start + self._batch_size]
            batch_docs = documents[start : start + self._batch_size]
            pairs = [(query, t) for t in batch_texts]
            scores = await asyncio.to_thread(model.predict, pairs)
            for idx, score in enumerate(scores):
                if score < self._threshold:
                    continue

                reranked.append(
                    replace(
                        batch_docs[idx],
                        score=float(score),
                        metadata={
                            **batch_docs[idx].metadata,
                            "rerank_score": float(score),
                        },
                    )
                )

        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[:top_k]

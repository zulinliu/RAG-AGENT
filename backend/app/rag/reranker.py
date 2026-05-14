"""Cross-Encoder reranking module with multi-provider support.

Providers:
  - tei:         HuggingFace TEI Docker (primary, recommended)
  - siliconflow: 硅基流动 API (cloud, same bge-reranker models)
  - cohere:      Cohere rerank API
  - jina:        Jina rerank API
  - custom:      any compatible endpoint
  - local-py:    load model in-process via sentence-transformers (dev only)
"""

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
    """Cross-Encoder reranker with multi-provider support."""

    def __init__(
        self,
        provider: str = "tei",
        api_url: str = "",
        model_name: str = "BAAI/bge-reranker-v2-m3",
        threshold: float = DEFAULT_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
        api_key: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self._api_url = api_url
        self._model_name = model_name
        self._threshold = threshold
        self._batch_size = batch_size
        self._api_key = api_key
        self._local_model: Any = None
        self._client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(timeout=60.0, headers=headers)
        return self._client

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
        """Rerank search results, returning the top_k highest-scoring documents."""
        if not documents:
            return []

        if self.provider == "local-py":
            return await self._rerank_local(query, documents, top_k)
        return await self._rerank_remote(query, documents, top_k)

    # ------------------------------------------------------------------
    # Remote mode (all providers except local-py)
    # ------------------------------------------------------------------

    async def _rerank_remote(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        texts = [d.content for d in documents]
        reranked: list[SearchResult] = []
        failed_docs: list[SearchResult] = []

        client = self._get_client()

        for start in range(0, len(texts), self._batch_size):
            batch_texts = texts[start : start + self._batch_size]
            batch_docs = documents[start : start + self._batch_size]
            payload = self._build_request(query, batch_texts)

            try:
                resp = await client.post(self._api_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                results = self._parse_response(data)
            except Exception:
                logger.exception("Rerank API call failed, degrading to original scores")
                failed_docs.extend(batch_docs)
                continue

            for item in results:
                idx = item["index"]
                score = item["score"]
                if score < self._threshold:
                    continue
                reranked.append(
                    replace(
                        batch_docs[idx],
                        score=score,
                        metadata={**batch_docs[idx].metadata, "rerank_score": score},
                    )
                )

        # 降级：失败批次按原始分数直接返回
        reranked.extend(failed_docs)
        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[:top_k]

    def _build_request(self, query: str, documents: list[str]) -> dict[str, Any]:
        """Build rerank request payload based on provider type."""
        if self.provider == "tei":
            return {
                "query": query,
                "texts": documents,
                "return_text": False,
            }
        # siliconflow / cohere / jina / openai-compatible / custom
        return {
            "model": self._model_name,
            "query": query,
            "documents": documents,
        }

    def _parse_response(self, data: Any) -> list[dict[str, Any]]:
        """Parse rerank response handling multiple formats."""
        # TEI format: [{"index": 0, "score": 0.95}, ...]
        if isinstance(data, list) and len(data) > 0:
            return [
                {"index": item.get("index", i), "score": float(item.get("score", 0.0))}
                for i, item in enumerate(data)
            ]

        # Cohere / siliconflow / custom format: {"results": [...]}
        if isinstance(data, dict):
            results = data.get("results", [])
            if isinstance(results, list):
                return [
                    {
                        "index": item.get("index", 0),
                        "score": float(
                            item.get("relevance_score", item.get("relevance", item.get("score", 0.0)))
                        ),
                    }
                    for item in results
                ]

        return []

    # ------------------------------------------------------------------
    # Local mode (in-process sentence-transformers)
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

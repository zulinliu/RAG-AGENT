"""Cross-Encoder 重排序模块。"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from app.rag.retriever import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.3
DEFAULT_BATCH_SIZE = 32
DEFAULT_TOP_K = 10
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


class CrossEncoderReranker:
    """基于 bge-reranker-v2-m3 的 Cross-Encoder 重排序器。

    支持两种模式:
      1. 本地模式 — 通过 sentence-transformers 加载模型。
      2. HTTP 模式 — 调用远程 reranker HTTP 服务。

    优先使用 HTTP 模式；当 reranker_url 为 None 时回退到本地模式。
    """

    def __init__(
        self,
        reranker_url: str | None = None,
        model_name: str = RERANKER_MODEL,
        threshold: float = DEFAULT_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._reranker_url = reranker_url
        self._model_name = model_name
        self._threshold = threshold
        self._batch_size = batch_size
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
        """对检索结果重排序，返回 top_k 个高分文档。

        低于 threshold 的文档将被剔除。
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

        async with httpx.AsyncClient(timeout=60.0) as client:
            for start in range(0, len(texts), self._batch_size):
                batch_texts = texts[start : start + self._batch_size]
                batch_docs = documents[start : start + self._batch_size]
                payload = {
                    "model": self._model_name,
                    "query": query,
                    "documents": batch_texts,
                }
                try:
                    resp = await client.post(
                        f"{self._reranker_url}/rerank",
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])
                except Exception:
                    logger.exception("HTTP rerank call failed")
                    continue

                for item in results:
                    idx = item.get("index", 0)
                    score = float(item.get("relevance_score", 0.0))
                    if score < self._threshold:
                        continue
                    from dataclasses import replace

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
                from dataclasses import replace

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

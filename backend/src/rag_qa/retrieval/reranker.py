from __future__ import annotations

import logging

import httpx

from rag_qa.retrieval.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


class Reranker:
    def __init__(
        self,
        api_base: str = "http://localhost:8002",
        api_key: str = "",
        model_name: str = "BAAI/bge-reranker-v2-m3",
        threshold: float = 0.3,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._threshold = threshold
        self._client = httpx.AsyncClient(timeout=60.0)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        documents = [chunk.content for chunk in chunks]

        resp = await self._client.post(
            f"{self._api_base}/rerank",
            json={
                "query": query,
                "documents": documents,
                "top_k": top_k,
                "model": self._model_name,
            },
            headers=self._build_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

        results: list[RetrievedChunk] = []
        for item in data.get("results", []):
            index = item.get("index", 0)
            score = item.get("relevance_score", 0.0)
            if score < self._threshold:
                continue
            reranked_chunk = chunks[index].model_copy(update={
                "score": score,
                "source": "reranked",
            })
            results.append(reranked_chunk)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

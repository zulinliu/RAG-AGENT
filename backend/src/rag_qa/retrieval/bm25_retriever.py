from __future__ import annotations

import logging

from rag_qa.retrieval.es_client import ESManager
from rag_qa.retrieval.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    def __init__(self, es_manager: ESManager) -> None:
        self._es = es_manager

    async def retrieve(
        self,
        query: str,
        project_id: str,
        top_k: int = 50,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        hits = self._es.search(
            query=query,
            project_id=project_id,
            top_k=top_k,
            filters=filters,
        )

        chunks: list[RetrievedChunk] = []
        for hit in hits:
            hierarchy = hit.get("hierarchy", [])
            if isinstance(hierarchy, str):
                hierarchy = [hierarchy]
            chunk = RetrievedChunk(
                chunk_id=hit.get("chunk_id", ""),
                doc_id=hit.get("doc_id", ""),
                project_id=hit.get("project_id", project_id),
                content=hit.get("content", ""),
                chunk_type=hit.get("chunk_type", ""),
                parent_title=hit.get("parent_title"),
                hierarchy=hierarchy,
                score=hit.get("_score", 0.0),
                source="bm25",
                metadata={},
            )
            chunks.append(chunk)
        return chunks

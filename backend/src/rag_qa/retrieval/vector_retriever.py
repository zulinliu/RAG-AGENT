from __future__ import annotations

import logging

from rag_qa.retrieval.milvus_client import MilvusManager
from rag_qa.retrieval.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


class VectorRetriever:
    def __init__(self, milvus_manager: MilvusManager, embedding_client) -> None:
        self._milvus = milvus_manager
        self._embedding = embedding_client

    async def retrieve(
        self,
        query: str,
        project_id: str,
        top_k: int = 50,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = await self._embedding.encode_single(query)
        hits = self._milvus.search(
            query_vector=query_vector,
            project_id=project_id,
            top_k=top_k,
            filters=filters,
        )

        chunks: list[RetrievedChunk] = []
        for hit in hits:
            chunk = RetrievedChunk(
                chunk_id=hit.get("chunk_id", ""),
                doc_id=hit.get("doc_id", ""),
                project_id=hit.get("project_id", project_id),
                content=hit.get("content", ""),
                chunk_type=hit.get("chunk_type", ""),
                parent_title=hit.get("parent_title"),
                hierarchy=hit.get("hierarchy", []),
                score=hit.get("score", 0.0),
                source="vector",
                metadata={},
            )
            chunks.append(chunk)
        return chunks

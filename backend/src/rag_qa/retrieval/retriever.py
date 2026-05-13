from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from rag_qa.retrieval.bm25_retriever import BM25Retriever
    from rag_qa.retrieval.query_optimizer import QueryOptimizer
    from rag_qa.retrieval.reranker import Reranker
    from rag_qa.retrieval.rrf_fusion import RRFFusion
    from rag_qa.retrieval.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    project_id: str
    content: str
    chunk_type: str
    parent_title: str | None = None
    hierarchy: list[str] = []
    score: float
    source: str
    metadata: dict = {}


class HybridRetriever:
    def __init__(
        self,
        vector_retriever: VectorRetriever,
        bm25_retriever: BM25Retriever,
        rrf_fusion: RRFFusion,
        reranker: Reranker,
        query_optimizer: QueryOptimizer,
        embedding_client=None,
    ):
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever
        self._rrf_fusion = rrf_fusion
        self._reranker = reranker
        self._query_optimizer = query_optimizer
        self._embedding_client = embedding_client

    async def retrieve(
        self,
        query: str,
        project_id: str,
        top_k: int = 10,
        use_rerank: bool = True,
        use_query_rewrite: bool = True,
    ) -> list[RetrievedChunk]:
        optimized_query = query
        if use_query_rewrite:
            optimized_query = await self._query_optimizer.rewrite_query(query)

        vector_task = self._vector_retriever.retrieve(
            query=optimized_query, project_id=project_id, top_k=50
        )
        bm25_task = self._bm25_retriever.retrieve(
            query=optimized_query, project_id=project_id, top_k=50
        )
        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)

        fused_results = self._rrf_fusion.fuse([vector_results, bm25_results])

        if use_rerank and fused_results:
            reranked_results = await self._reranker.rerank(
                query=optimized_query, chunks=fused_results, top_k=top_k
            )
            return reranked_results

        return fused_results[:top_k]

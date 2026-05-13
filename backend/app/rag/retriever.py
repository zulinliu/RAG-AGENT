"""混合检索引擎 — 支持 Milvus 向量检索 + Elasticsearch BM25 检索。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from pymilvus import MilvusClient
from elasticsearch import AsyncElasticsearch

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """单条检索结果。"""

    chunk_id: str
    content: str
    score: float
    source: str  # "vector" | "bm25"
    metadata: dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """混合检索引擎，并行执行向量检索和 BM25 检索，结果由上层融合。"""

    def __init__(
        self,
        milvus_client: MilvusClient,
        es_client: AsyncElasticsearch,
        collection_name: str = "rag_chunks",
        es_index: str = "rag_chunks",
    ) -> None:
        self._milvus = milvus_client
        self._es = es_client
        self._collection_name = collection_name
        self._es_index = es_index

    # ------------------------------------------------------------------
    # Vector search (Milvus ANN)
    # ------------------------------------------------------------------

    async def vector_search(
        self,
        query_embedding: list[float],
        project_id: str,
        top_k: int = 50,
    ) -> list[SearchResult]:
        """在 Milvus 中执行 ANN 向量检索。"""
        try:
            results = await asyncio.to_thread(
                self._milvus.search,
                collection_name=self._collection_name,
                data=[query_embedding],
                limit=top_k,
                output_fields=["chunk_id", "content", "metadata"],
                filter=f'project_id == "{project_id}"',
                search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
            )
            search_results: list[SearchResult] = []
            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    search_results.append(
                        SearchResult(
                            chunk_id=entity.get("chunk_id", str(hit.get("id", ""))),
                            content=entity.get("content", ""),
                            score=float(hit.get("distance", 0.0)),
                            source="vector",
                            metadata=entity.get("metadata", {}),
                        )
                    )
            logger.info(
                "vector_search returned %d results for project=%s",
                len(search_results),
                project_id,
            )
            return search_results
        except Exception:
            logger.exception("vector_search failed for project=%s", project_id)
            return []

    # ------------------------------------------------------------------
    # BM25 search (Elasticsearch)
    # ------------------------------------------------------------------

    async def bm25_search(
        self,
        query_text: str,
        project_id: str,
        top_k: int = 50,
    ) -> list[SearchResult]:
        """在 Elasticsearch 中执行 BM25 文本检索。"""
        try:
            body: dict[str, Any] = {
                "size": top_k,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query_text,
                                    "fields": ["content^2", "title^1"],
                                    "type": "best_fields",
                                }
                            }
                        ],
                        "filter": [{"term": {"project_id": project_id}}],
                    }
                },
                "_source": ["chunk_id", "content", "metadata"],
            }
            resp = await self._es.search(index=self._es_index, body=body)
            search_results: list[SearchResult] = []
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                search_results.append(
                    SearchResult(
                        chunk_id=src.get("chunk_id", hit["_id"]),
                        content=src.get("content", ""),
                        score=float(hit["_score"]),
                        source="bm25",
                        metadata=src.get("metadata", {}),
                    )
                )
            logger.info(
                "bm25_search returned %d results for project=%s",
                len(search_results),
                project_id,
            )
            return search_results
        except Exception:
            logger.exception("bm25_search failed for project=%s", project_id)
            return []

    # ------------------------------------------------------------------
    # Hybrid search (parallel)
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        project_id: str,
        vector_top_k: int = 50,
        bm25_top_k: int = 50,
    ) -> list[list[SearchResult]]:
        """并行执行向量检索和 BM25 检索，返回两路结果列表。

        调用方负责将两路结果送入 RRF 融合。
        """
        vector_task = self.vector_search(
            query_embedding, project_id, top_k=vector_top_k
        )
        bm25_task = self.bm25_search(query_text, project_id, top_k=bm25_top_k)
        vector_results, bm25_results = await asyncio.gather(
            vector_task, bm25_task
        )
        return [vector_results, bm25_results]

from __future__ import annotations

import logging
from typing import Any

import httpx

from rag_qa.pipeline.chunker import ChunkResult
from rag_qa.pipeline.metadata_extractor import DocumentMetadata
from rag_qa.retrieval.es_client import ESManager
from rag_qa.retrieval.milvus_client import MilvusManager

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(
        self,
        api_base: str = "http://localhost:8001",
        api_key: str = "",
        model_name: str = "BAAI/bge-large-zh-v1.5",
        dimension: int = 1024,
    ):
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        self._client = httpx.AsyncClient(timeout=60.0)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.post(
                f"{self._api_base}/embeddings",
                json={"input": batch, "model": self._model_name},
                headers=self._build_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            for item in sorted_data:
                all_embeddings.append(item["embedding"])
        return all_embeddings

    async def encode_single(self, text: str) -> list[float]:
        result = await self.encode([text], batch_size=1)
        return result[0]


class DocumentIndexer:
    def __init__(
        self,
        milvus_manager: MilvusManager,
        es_manager: ESManager,
        embedding_client: EmbeddingClient,
    ):
        self._milvus = milvus_manager
        self._es = es_manager
        self._embedding = embedding_client

    async def index_document(
        self, chunks: list[ChunkResult], metadata: DocumentMetadata
    ) -> int:
        if not chunks:
            return 0

        texts = [chunk.content for chunk in chunks]
        vectors = await self._embedding.encode(texts)

        milvus_chunks: list[dict[str, Any]] = []
        es_chunks: list[dict[str, Any]] = []

        for chunk, vector in zip(chunks, vectors):
            milvus_chunks.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": metadata.doc_id,
                    "project_id": metadata.project_id,
                    "content_vector": vector,
                    "chunk_type": chunk.chunk_type.value,
                    "parent_title": chunk.parent_title or "",
                }
            )

            es_chunks.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": metadata.doc_id,
                    "project_id": metadata.project_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type.value,
                    "parent_title": chunk.parent_title or "",
                    "hierarchy": chunk.hierarchy,
                    "author": metadata.author,
                    "created_at": metadata.created_at.isoformat()
                    if metadata.created_at
                    else None,
                    "modified_at": metadata.modified_at.isoformat()
                    if metadata.modified_at
                    else None,
                }
            )

        self._milvus.insert_chunks(milvus_chunks)
        self._es.index_chunks(metadata.project_id, es_chunks)

        return len(chunks)

from __future__ import annotations

import logging
from typing import Any

from pymilvus import DataType, MilvusClient

logger = logging.getLogger(__name__)

COLLECTION_NAME = "doc_chunks"


class MilvusManager:
    def __init__(self, host: str = "localhost", port: int = 19530) -> None:
        self._host = host
        self._port = port
        self._client = MilvusClient(uri=f"http://{host}:{port}")

    def create_collection(self) -> None:
        if self._client.has_collection(COLLECTION_NAME):
            return

        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="project_id", datatype=DataType.VARCHAR, max_length=64, is_partition_key=True)
        schema.add_field(field_name="content_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field(field_name="chunk_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=512)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="content_vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 256},
        )
        index_params.add_index(field_name="chunk_id", index_type="STL_SORT")
        index_params.add_index(field_name="doc_id", index_type="STL_SORT")
        index_params.add_index(field_name="project_id", index_type="STL_SORT")

        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
            num_partitions=64,
        )

    def insert_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        self._client.upsert(collection_name=COLLECTION_NAME, data=chunks)

    def search(
        self,
        query_vector: list[float],
        project_id: str,
        top_k: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        filter_expr = f'project_id == "{project_id}"'
        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_expr += f' && {key} == "{value}"'
                elif isinstance(value, list):
                    items = ", ".join(f'"{v}"' for v in value)
                    filter_expr += f" && {key} in [{items}]"
                else:
                    filter_expr += f" && {key} == {value}"

        results = self._client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=["chunk_id", "doc_id", "project_id", "chunk_type", "parent_title"],
            search_params={"metric_type": "COSINE", "params": {"ef": 256}},
        )

        hits = []
        for result in results[0]:
            hit = dict(result["entity"])
            hit["score"] = result["distance"]
            hits.append(hit)
        return hits

    def delete_by_doc_id(self, doc_id: str) -> None:
        self._client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'doc_id == "{doc_id}"',
        )

    def delete_by_project_id(self, project_id: str) -> None:
        self._client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'project_id == "{project_id}"',
        )

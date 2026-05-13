from __future__ import annotations

import logging
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "doc_chunks_template"
INDEX_PREFIX = "doc_chunks_"

_TEMPLATE_BODY = {
    "index_patterns": [f"{INDEX_PREFIX}*"],
    "template": {
        "settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "ik_max_word": {
                        "type": "custom",
                        "tokenizer": "ik_max_word",
                    },
                    "ik_smart": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                    },
                },
            },
        },
        "mappings": {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "project_id": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "search_analyzer": "ik_smart",
                },
                "chunk_type": {"type": "keyword"},
                "parent_title": {"type": "text", "analyzer": "ik_max_word"},
                "hierarchy": {"type": "keyword"},
                "author": {"type": "keyword"},
                "created_at": {"type": "date"},
                "modified_at": {"type": "date"},
            },
        },
    },
}


class ESManager:
    def __init__(self, hosts: list[str] | None = None) -> None:
        self._hosts = hosts or ["http://localhost:9200"]
        self._es = Elasticsearch(hosts=self._hosts)

    def create_index_template(self) -> None:
        if self._es.indices.exists_index_template(name=TEMPLATE_NAME):
            return
        self._es.indices.put_index_template(name=TEMPLATE_NAME, body=_TEMPLATE_BODY)

    def create_index(self, project_id: str) -> None:
        index_name = f"{INDEX_PREFIX}{project_id}"
        if self._es.indices.exists(index=index_name):
            return
        self._es.indices.create(index=index_name)

    def index_chunks(self, project_id: str, chunks: list[dict]) -> None:
        if not chunks:
            return
        index_name = f"{INDEX_PREFIX}{project_id}"

        actions = []
        for chunk in chunks:
            action = {
                "_index": index_name,
                "_id": chunk["chunk_id"],
                "_source": chunk,
            }
            actions.append(action)

        bulk(self._es, actions)

    def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        index_name = f"{INDEX_PREFIX}{project_id}"

        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content^3", "parent_title^1"],
                },
            },
        ]

        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    must.append({"terms": {key: value}})
                else:
                    must.append({"term": {key: value}})

        body = {
            "size": top_k,
            "query": {"bool": {"must": must}},
            "_source": {
                "excludes": [],
            },
        }

        resp = self._es.search(index=index_name, body=body)

        hits = []
        for hit in resp["hits"]["hits"]:
            source = hit["_source"]
            source["_score"] = hit["_score"]
            hits.append(source)
        return hits

    def delete_by_doc_id(self, project_id: str, doc_id: str) -> None:
        index_name = f"{INDEX_PREFIX}{project_id}"
        self._es.delete_by_query(
            index=index_name,
            body={"query": {"term": {"doc_id": doc_id}}},
        )

    def delete_index(self, project_id: str) -> None:
        index_name = f"{INDEX_PREFIX}{project_id}"
        if self._es.indices.exists(index=index_name):
            self._es.indices.delete(index=index_name)

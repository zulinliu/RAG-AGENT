from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis


class CacheService:
    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get_query_cache(self, query: str, project_id: str) -> dict[str, Any] | None:
        key = self._build_query_key(query, project_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        loaded_cache: dict[str, Any] = json.loads(data)
        return loaded_cache

    async def set_query_cache(self, query: str, project_id: str, result: dict[str, Any], ttl: int = 3600) -> None:
        key = self._build_query_key(query, project_id)
        data = json.dumps(result, ensure_ascii=False)
        await self._redis.set(key, data, ex=ttl)

    async def get_embedding_cache(self, text_hash: str) -> list[float] | None:
        key = f"emb:{text_hash}"
        data = await self._redis.get(key)
        if data is None:
            return None
        loaded: list[float] = json.loads(data)
        return loaded

    async def set_embedding_cache(self, text_hash: str, embedding: list[float], ttl: int = 86400) -> None:
        key = f"emb:{text_hash}"
        data = json.dumps(embedding)
        await self._redis.set(key, data, ex=ttl)

    @staticmethod
    def _build_query_key(query: str, project_id: str) -> str:
        raw = f"{project_id}:{query}"
        h = hashlib.md5(raw.encode()).hexdigest()
        return f"query:{h}"

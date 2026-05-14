"""基于 Redis 的查询缓存 — 缓存 embedding 向量和 CRAG 查询结果。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# TTL 常量（秒）
_EMBEDDING_TTL = 3600  # 1 小时
_RESULT_TTL = 300  # 5 分钟

# 键前缀
_EMB_PREFIX = "emb"
_QA_PREFIX = "qa"


def _sha256(text: str) -> str:
    """返回 *text* 的 SHA-256 十六进制摘要。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class QueryCache:
    """基于 Redis 的查询缓存，Redis 不可用时优雅降级为空操作。"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._url = redis_url
        self._redis: aioredis.Redis | None = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """初始化 Redis 连接。连接失败时仅记录警告，不抛异常。"""
        try:
            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await self._redis.ping()
            logger.info("QueryCache: Redis connected (%s)", self._url)
        except Exception:
            logger.warning("QueryCache: Redis unavailable, caching disabled")
            self._redis = None

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                logger.debug("QueryCache: error closing Redis connection", exc_info=True)
            finally:
                self._redis = None

    # ------------------------------------------------------------------
    # Embedding 缓存
    # ------------------------------------------------------------------

    async def get_embedding(
        self, query: str, project_id: str
    ) -> list[float] | None:
        """获取缓存的 embedding 向量，未命中或出错时返回 ``None``。"""
        redis = self._redis
        if redis is None:
            return None

        key = f"{_EMB_PREFIX}:{_sha256(query + project_id)}"
        try:
            raw: str | None = await redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("QueryCache.get_embedding failed", exc_info=True)
            return None

    async def set_embedding(
        self, query: str, project_id: str, embedding: list[float]
    ) -> None:
        """写入 embedding 向量缓存。"""
        redis = self._redis
        if redis is None:
            return

        key = f"{_EMB_PREFIX}:{_sha256(query + project_id)}"
        try:
            await redis.set(key, json.dumps(embedding), ex=_EMBEDDING_TTL)
        except Exception:
            logger.debug("QueryCache.set_embedding failed", exc_info=True)

    # ------------------------------------------------------------------
    # 查询结果缓存
    # ------------------------------------------------------------------

    async def get_result(
        self, query: str, project_id: str
    ) -> dict[str, Any] | None:
        """获取缓存的 CRAG 查询结果，未命中或出错时返回 ``None``。"""
        redis = self._redis
        if redis is None:
            return None

        key = f"{_QA_PREFIX}:{project_id}:{_sha256(query)}"
        try:
            raw: str | None = await redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("QueryCache.get_result failed", exc_info=True)
            return None

    async def set_result(
        self, query: str, project_id: str, result: dict[str, Any]
    ) -> None:
        """写入 CRAG 查询结果缓存。"""
        redis = self._redis
        if redis is None:
            return

        key = f"{_QA_PREFIX}:{project_id}:{_sha256(query)}"
        try:
            await redis.set(key, json.dumps(result, ensure_ascii=False), ex=_RESULT_TTL)
        except Exception:
            logger.debug("QueryCache.set_result failed", exc_info=True)

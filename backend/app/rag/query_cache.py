"""语义查询缓存 — 基于 embedding 余弦相似度的近义词缓存。

相比精确哈希匹配，语义缓存能识别语义相近的查询并返回缓存结果，
例如 "项目时间线" 和 "项目进度安排" 会命中同一缓存条目。

降级策略：Redis 不可用时退化为空操作。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# TTL 常量
_EMBEDDING_TTL = 3600       # embedding 缓存 1 小时
_RESULT_TTL = 1800          # 查询结果缓存 30 分钟（与知识库更新周期对齐）
_SEMANTIC_TTL = 1800        # 语义索引条目 TTL

# 键前缀
_EMB_PREFIX = "emb"
_QA_PREFIX = "qa"
_SEMANTIC_PREFIX = "sem"    # 语义索引

# 语义匹配阈值（余弦相似度）
_SIMILARITY_THRESHOLD = 0.92


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class QueryCache:
    """语义查询缓存，基于 Redis。

    查询结果缓存流程：
    1. 将查询文本 embedding 后，与 Redis 中已缓存的 embedding 逐一比对
    2. 找到相似度超过阈值的条目时，返回对应缓存结果
    3. 未命中时正常执行管线，将结果和 embedding 一起缓存
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        embedding_model_name: str = "",
    ) -> None:
        self._url = redis_url
        self._redis: aioredis.Redis | None = None
        self._embedding_model_name = embedding_model_name
        self._embedding_fn: Any = None

    def set_embedding_fn(self, fn: Any) -> None:
        """注入 embedding 函数，用于语义缓存计算查询向量。"""
        self._embedding_fn = fn

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def init(self) -> None:
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
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                logger.debug("QueryCache: error closing Redis connection", exc_info=True)
            finally:
                self._redis = None

    # ------------------------------------------------------------------
    # Embedding 缓存（精确匹配，用于避免重复向量化）
    # ------------------------------------------------------------------

    async def get_embedding(
        self, query: str, project_id: str
    ) -> list[float] | None:
        redis = self._redis
        if redis is None:
            return None

        key = f"{_EMB_PREFIX}:{self._embedding_model_name}:{_sha256(query + project_id)}"
        try:
            raw: str | None = await redis.get(key)
            if raw is None:
                self._record_miss()
                return None
            self._record_hit()
            return json.loads(raw)
        except Exception:
            logger.debug("QueryCache.get_embedding failed", exc_info=True)
            return None

    async def set_embedding(
        self, query: str, project_id: str, embedding: list[float]
    ) -> None:
        redis = self._redis
        if redis is None:
            return

        key = f"{_EMB_PREFIX}:{self._embedding_model_name}:{_sha256(query + project_id)}"
        try:
            await redis.set(key, json.dumps(embedding), ex=_EMBEDDING_TTL)
        except Exception:
            logger.debug("QueryCache.set_embedding failed", exc_info=True)

    # ------------------------------------------------------------------
    # 查询结果缓存（语义匹配）
    # ------------------------------------------------------------------

    async def get_result(
        self, query: str, project_id: str
    ) -> dict[str, Any] | None:
        """语义检索缓存结果。

        1. 生成查询的 embedding
        2. 扫描该项目下所有缓存条目的 embedding
        3. 找到相似度超过阈值的条目，返回对应结果
        """
        redis = self._redis
        if redis is None:
            return None

        # 尝试精确匹配（快速路径）
        exact_key = f"{_QA_PREFIX}:{project_id}:{_sha256(query)}"
        try:
            raw = await redis.get(exact_key)
            if raw is not None:
                self._record_hit()
                return json.loads(raw)
        except Exception:
            pass

        # 语义匹配
        if self._embedding_fn is None:
            self._record_miss()
            return None

        try:
            query_vec = await self._embedding_fn(query)
        except Exception:
            logger.debug("QueryCache: embedding for semantic search failed")
            self._record_miss()
            return None

        # 扫描该项目下的语义索引
        pattern = f"{_SEMANTIC_PREFIX}:{project_id}:*"
        try:
            best_match_key = None
            best_score = 0.0

            async for key in redis.scan_iter(match=pattern, count=50):
                raw = await redis.get(key)
                if raw is None:
                    continue
                cached = json.loads(raw)
                cached_vec = cached.get("embedding")
                if not cached_vec:
                    continue

                sim = _cosine_similarity(query_vec, cached_vec)
                if sim > best_score:
                    best_score = sim
                    best_match_key = cached.get("result_key")

            if best_score >= _SIMILARITY_THRESHOLD and best_match_key:
                result_raw = await redis.get(best_match_key)
                if result_raw:
                    self._record_hit()
                    logger.info(
                        "QueryCache: semantic hit (sim=%.3f) for '%s'",
                        best_score, query,
                    )
                    return json.loads(result_raw)

        except Exception:
            logger.debug("QueryCache: semantic search failed", exc_info=True)

        self._record_miss()
        return None

    async def set_result(
        self, query: str, project_id: str, result: dict[str, Any]
    ) -> None:
        """缓存查询结果，同时建立语义索引。"""
        redis = self._redis
        if redis is None:
            return

        result_key = f"{_QA_PREFIX}:{project_id}:{_sha256(query)}"

        try:
            # 存储结果
            await redis.set(
                result_key,
                json.dumps(result, ensure_ascii=False),
                ex=_RESULT_TTL,
            )

            # 建立语义索引条目
            if self._embedding_fn is not None:
                try:
                    query_vec = await self._embedding_fn(query)
                    semantic_key = f"{_SEMANTIC_PREFIX}:{project_id}:{_sha256(query)}"
                    await redis.set(
                        semantic_key,
                        json.dumps({
                            "embedding": query_vec,
                            "result_key": result_key,
                            "query": query[:200],
                        }),
                        ex=_SEMANTIC_TTL,
                    )
                except Exception:
                    logger.debug("QueryCache: semantic index write failed")
        except Exception:
            logger.debug("QueryCache.set_result failed", exc_info=True)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _record_hit() -> None:
        try:
            from app.middleware.metrics import RAG_CACHE_HITS_TOTAL
            RAG_CACHE_HITS_TOTAL.inc()
        except Exception:
            pass

    @staticmethod
    def _record_miss() -> None:
        try:
            from app.middleware.metrics import RAG_CACHE_MISSES_TOTAL
            RAG_CACHE_MISSES_TOTAL.inc()
        except Exception:
            pass

"""RRF (Reciprocal Rank Fusion) 融合算法。"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from app.rag.retriever import SearchResult

logger = logging.getLogger(__name__)


def rrf_fusion(
    results_list: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """将多路检索结果按 RRF 公式融合为单一排序。

    公式: RRF_score(d) = sum_i(1 / (k + rank_i(d)))

    Args:
        results_list: 多路检索结果，每路为一个 SearchResult 列表。
        k: RRF 常数，默认 60。较大的 k 使排名靠后的文档得分更平滑。

    Returns:
        融合并按 RRF 分数降序排列的 SearchResult 列表。
        每条结果的 score 字段存储 RRF 分数，metadata 中保留原始分数。
    """
    accumulated: dict[str, dict[str, Any]] = {}

    for retrieval_index, results in enumerate(results_list):
        for rank, item in enumerate(results, start=1):
            contribution = 1.0 / (k + rank)
            if item.chunk_id not in accumulated:
                accumulated[item.chunk_id] = {
                    "result": item,
                    "rrf_score": 0.0,
                    "original_scores": [],
                }
            accumulated[item.chunk_id]["rrf_score"] += contribution
            accumulated[item.chunk_id]["original_scores"].append(
                {"source": item.source, "rank": rank, "original_score": item.score}
            )

    fused: list[SearchResult] = []
    for entry in accumulated.values():
        result = replace(
            entry["result"],
            score=entry["rrf_score"],
            metadata={
                **entry["result"].metadata,
                "rrf_score": entry["rrf_score"],
                "original_scores": entry["original_scores"],
            },
        )
        fused.append(result)

    fused.sort(key=lambda r: r.score, reverse=True)
    logger.info("rrf_fusion produced %d fused results", len(fused))
    return fused

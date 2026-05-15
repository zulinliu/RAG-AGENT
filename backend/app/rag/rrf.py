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

    最终分数乘以 k 进行归一化，使分数范围接近 0-1。

    Args:
        results_list: 多路检索结果，每路为一个 SearchResult 列表。
        k: RRF 常数，默认 60。
            - 较大的 k 使排名靠后的文档得分更平滑，减少头部偏差。
            - 较小的 k 放大排名差异，让靠前的文档获得更大优势。
            - 调优建议: 如果检索路数多(>3)，可适当增大 k(100-200)；
              如果只有 2 路且想强化头部，可减小 k(30-50)。

    Returns:
        融合并按 RRF 分数降序排列的 SearchResult 列表。
        每条结果的 score 字段存储归一化后的 RRF 分数(约 0-1)，
        metadata 中保留原始分数和 rrf_score。
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
        normalized_score = entry["rrf_score"] * k
        result = replace(
            entry["result"],
            score=normalized_score,
            metadata={
                **entry["result"].metadata,
                "rrf_score": normalized_score,
                "rrf_score_raw": entry["rrf_score"],
                "original_scores": entry["original_scores"],
            },
        )
        fused.append(result)

    fused.sort(key=lambda r: r.score, reverse=True)
    logger.info("rrf_fusion produced %d fused results", len(fused))
    return fused

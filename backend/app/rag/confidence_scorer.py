"""置信度评分器 — 综合检索质量、引用覆盖和答案合理性。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 权重配置
WEIGHT_RETRIEVAL = 0.4
WEIGHT_CITATION = 0.3
WEIGHT_ANSWER = 0.3

# 低置信度阈值
LOW_CONFIDENCE_THRESHOLD = 0.6


class ConfidenceScorer:
    """综合置信度评分器。"""

    @staticmethod
    def score(
        retrieval_scores: list[float],
        citation_coverage: float,
        answer_length: int,
    ) -> float:
        """计算综合置信度分数 (0-1)。

        Args:
            retrieval_scores: 检索文档的相关性分数列表。
            citation_coverage: 引用覆盖率 (0-1)。
            answer_length: 答案文本长度（字符数）。

        Returns:
            置信度分数 (0-1)。
        """
        # 1. 检索质量: 取平均归一化分数（假设 rerank score 范围 0-1）
        if retrieval_scores:
            avg_retrieval = sum(retrieval_scores) / len(retrieval_scores)
            retrieval_quality = min(avg_retrieval, 1.0)
        else:
            retrieval_quality = 0.0

        # 2. 引用覆盖: 直接使用
        citation_score = min(citation_coverage, 1.0)

        # 3. 答案合理性: 基于长度启发式
        #    太短(< 30 字)或太长(> 3000 字)都降低分数
        if answer_length < 10:
            answer_reasonableness = 0.1
        elif answer_length < 30:
            answer_reasonableness = 0.4
        elif answer_length <= 3000:
            answer_reasonableness = min(answer_length / 500.0, 1.0)
            answer_reasonableness = max(answer_reasonableness, 0.5)
        else:
            answer_reasonableness = max(1.0 - (answer_length - 3000) / 5000.0, 0.3)

        # 加权综合
        confidence = (
            WEIGHT_RETRIEVAL * retrieval_quality
            + WEIGHT_CITATION * citation_score
            + WEIGHT_ANSWER * answer_reasonableness
        )
        confidence = round(max(0.0, min(1.0, confidence)), 4)

        if confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.warning(
                "low confidence answer: %.2f (retrieval=%.2f, citation=%.2f, answer=%.2f)",
                confidence,
                retrieval_quality,
                citation_score,
                answer_reasonableness,
            )
        else:
            logger.info("confidence score: %.2f", confidence)

        return confidence

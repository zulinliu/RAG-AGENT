"""引用验证器 — 检查答案中的 [来源N] 引用是否合法。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CITATION_PATTERN = re.compile(r"\[来源(\d+)\]")


@dataclass
class VerificationResult:
    """引用验证结果。"""

    is_valid: bool
    total_citations: int = 0
    valid_citations: list[int] = field(default_factory=list)
    fake_citations: list[int] = field(default_factory=list)
    citation_coverage: float = 0.0


class CitationVerifier:
    """验证答案中 [来源N] 引用的合法性。"""

    @staticmethod
    def verify(
        answer_text: str,
        retrieved_docs: list,  # list[SearchResult]
    ) -> VerificationResult:
        """提取并验证答案中所有引用。

        Args:
            answer_text: 生成的答案文本。
            retrieved_docs: 实际检索到的文档列表。

        Returns:
            VerificationResult 包含合法/虚假引用信息。
        """
        max_source = len(retrieved_docs)
        if max_source == 0:
            return VerificationResult(is_valid=False, total_citations=0)

        raw_citations = CITATION_PATTERN.findall(answer_text)
        citation_numbers = [int(n) for n in raw_citations]

        valid: list[int] = []
        fake: list[int] = []

        for num in set(citation_numbers):
            if 1 <= num <= max_source:
                valid.append(num)
            else:
                fake.append(num)

        valid.sort()
        fake.sort()

        # 引用覆盖率 = 引用的不重复文档数 / 总检索文档数
        coverage = len(valid) / max_source if max_source > 0 else 0.0

        result = VerificationResult(
            is_valid=len(fake) == 0,
            total_citations=len(citation_numbers),
            valid_citations=valid,
            fake_citations=fake,
            citation_coverage=round(coverage, 4),
        )

        if fake:
            logger.warning("fake citations detected: %s (max source=%d)", fake, max_source)
        else:
            logger.info(
                "citation verification passed: %d valid, coverage=%.2f%%",
                len(valid),
                coverage * 100,
            )

        return result

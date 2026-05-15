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

    @staticmethod
    def verify_claim_grounding(answer: str, docs: list) -> dict:
        """验证答案中的引用内容是否在引用文档中实际存在。

        对每个 [来源N] 标注的内容，检查其上下文是否与对应文档内容有足够重叠。
        """
        if not docs or not answer:
            return {"grounding_rate": 0.0, "ungrounded_citations": []}

        citation_pattern = re.compile(r"\[来源(\d+)\]")
        ungrounded: list[int] = []
        total_citations = 0

        # 按引用位置拆分答案，检查每个引用前的文本
        parts = citation_pattern.split(answer)

        for i in range(1, len(parts), 2):
            try:
                source_idx = int(parts[i]) - 1
            except (ValueError, IndexError):
                continue

            total_citations += 1
            if source_idx < 0 or source_idx >= len(docs):
                ungrounded.append(source_idx + 1)
                continue

            # 获取引用后的文本（该来源声明的实际内容）
            claim_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not claim_text:
                continue

            # 检查声明内容与文档的关键词重叠度
            doc_content = docs[source_idx].content if hasattr(docs[source_idx], "content") else str(docs[source_idx])

            # 简单关键词重叠检查：提取声明中的关键短语
            overlap_count = 0
            claim_phrases = [p.strip() for p in re.split(r"[，。、；！？\s]+", claim_text) if len(p.strip()) >= 3]
            for phrase in claim_phrases[:5]:  # 只检查前5个关键短语
                if phrase in doc_content:
                    overlap_count += 1

            # 如果没有任何关键短语在文档中出现，标记为未落地
            if claim_phrases and overlap_count == 0:
                ungrounded.append(source_idx + 1)

        grounding_rate = 1.0 - (len(ungrounded) / max(total_citations, 1))
        return {
            "grounding_rate": grounding_rate,
            "ungrounded_citations": ungrounded,
            "total_citations": total_citations,
        }

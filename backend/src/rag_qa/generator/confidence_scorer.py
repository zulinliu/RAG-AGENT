from __future__ import annotations

import re
from typing import Any

from rag_qa.generator.context_builder import RetrievedChunk


class ConfidenceScorer:
    def score(
        self,
        chunks: list[RetrievedChunk],
        answer: str,
        valid_citations: list[str],
        source_mapping: dict[str, Any],
    ) -> float:
        relevance_score = self._relevance_score(chunks)
        citation_score = self._citation_coverage(answer, valid_citations, source_mapping)
        length_score = self._length_score(answer)

        final = 0.4 * relevance_score + 0.3 * citation_score + 0.3 * length_score
        return max(0.0, min(1.0, final))

    def is_low_confidence(self, score: float, threshold: float = 0.6) -> bool:
        return score < threshold

    @staticmethod
    def _relevance_score(chunks: list[RetrievedChunk]) -> float:
        if not chunks:
            return 0.0
        total = sum(c.relevance_score for c in chunks)
        return total / len(chunks)

    @staticmethod
    def _citation_coverage(answer: str, valid_citations: list[str], source_mapping: dict[str, Any]) -> float:
        if not source_mapping:
            return 0.0
        sentences = re.split(r"[。！？；\n]", answer)
        factual_sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        if not factual_sentences:
            return 0.0
        cited_count = 0
        for sentence in factual_sentences:
            if re.search(r"\[来源\d+\]", sentence):
                cited_count += 1
        return cited_count / len(factual_sentences)

    @staticmethod
    def _length_score(answer: str) -> float:
        length = len(answer)
        if length == 0:
            return 0.0
        if length < 20:
            return length / 20.0 * 0.3
        if length <= 2000:
            return 1.0
        if length <= 5000:
            return 1.0 - (length - 2000) / 3000.0 * 0.5
        return 0.5

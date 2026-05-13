from __future__ import annotations

import re
from typing import Any


class CitationVerifier:
    def verify(self, answer: str, source_mapping: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
        citations = self._extract_citations(answer)
        valid_citations: list[str] = []
        invalid_citations: set[str] = set()

        for citation in citations:
            if citation in source_mapping:
                if citation not in valid_citations:
                    valid_citations.append(citation)
            else:
                invalid_citations.add(citation)

        cleaned_answer = answer
        for invalid in invalid_citations:
            pattern = re.compile(rf"\[来源{re.escape(invalid)}\]")
            cleaned_answer = pattern.sub("", cleaned_answer)

        return cleaned_answer, valid_citations

    def _extract_citations(self, text: str) -> list[str]:
        matches = re.findall(r"\[来源(\d+)\]", text)
        return matches

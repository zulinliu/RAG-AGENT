from __future__ import annotations

import re
from collections import Counter

from rag_qa.pipeline.parser_base import ParsedSection


class TextCleaner:

    WATERMARK_KEYWORDS = [
        "水印",
        "watermark",
        "样本",
        "sample",
        "草稿",
        "draft",
        "机密",
        "confidential",
        "内部使用",
        "internal use",
        "仅供参考",
        "for reference only",
        "禁止复制",
        "do not copy",
        "试用版",
        "trial version",
        "未注册",
        "unregistered",
    ]

    ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")

    MULTI_SPACE_RE = re.compile(r"[^\S\n]{2,}")

    MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

    ALLOWED_UNICODE_RE = re.compile(
        r"[^\u4e00-\u9fff\u3400-\u4dbf"
        r"\u0020-\u007e"
        r"\u3000-\u303f"
        r"\uff00-\uffef"
        r"\u2000-\u206f"
        r"\u00a0-\u00ff"
        r"\u2018-\u201d"
        r"\u201c-\u201d"
        r"\u2026"
        r"\u2014\u2013"
        r"\n\r\t]"
    )

    def clean(self, text: str) -> str:
        text = self._remove_headers_footers(text)
        text = self._remove_watermarks(text)
        text = self._remove_zero_width_chars(text)
        text = self._remove_special_unicode(text)
        text = self._normalize_whitespace(text)
        return text.strip()

    def clean_section(self, section: ParsedSection) -> ParsedSection:
        cleaned_content = self.clean(section.content)
        return ParsedSection(
            level=section.level,
            title=section.title,
            content=cleaned_content,
            chunk_type=section.chunk_type,
        )

    def _remove_headers_footers(self, text: str) -> str:
        lines = text.split("\n")
        if len(lines) < 4:
            return text

        line_counter = Counter(lines)
        repeated_lines = {line for line, count in line_counter.items() if count >= 3 and line.strip()}

        if not repeated_lines:
            return text

        filtered = [line for line in lines if line not in repeated_lines]
        return "\n".join(filtered)

    def _remove_watermarks(self, text: str) -> str:
        lines = text.split("\n")
        filtered: list[str] = []
        for line in lines:
            stripped = line.strip().lower()
            should_remove = False
            for keyword in self.WATERMARK_KEYWORDS:
                if keyword.lower() in stripped and len(stripped) < len(keyword) * 5:
                    should_remove = True
                    break
            if not should_remove:
                filtered.append(line)
        return "\n".join(filtered)

    def _remove_zero_width_chars(self, text: str) -> str:
        return self.ZERO_WIDTH_RE.sub("", text)

    def _remove_special_unicode(self, text: str) -> str:
        return self.ALLOWED_UNICODE_RE.sub("", text)

    def _normalize_whitespace(self, text: str) -> str:
        text = self.MULTI_SPACE_RE.sub(" ", text)
        text = self.MULTI_NEWLINE_RE.sub("\n\n", text)
        return text

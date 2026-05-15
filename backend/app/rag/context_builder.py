"""上下文构建器 — 将重排序后的文档组织为结构化上下文。"""

from __future__ import annotations

import logging
from typing import Any

from app.rag.retriever import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT_TOKENS = 4000
APPROX_CHARS_PER_TOKEN = 1.5  # 中文约 1.5 字符/token（中文文本每个 token 约覆盖 1.5 个字符）


class ContextBuilder:
    """将重排序后的文档构建为结构化上下文字符串。"""

    def __init__(self, max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS) -> None:
        self._max_context_tokens = max_context_tokens

    def build_context(self, reranked_docs: list[SearchResult]) -> str:
        """构建结构化上下文，按格式组织每个来源。

        格式:
            [参考资料]
            [来源1] 文档标题：XXX | 章节：XXX | 作者：XXX | 日期：XXX
            内容：...
            [来源2] ...
        """
        if not reranked_docs:
            return "[参考资料]\n（无可用参考资料）"

        # 去重: Jaccard 相似度 > 0.8 的文档只保留排名更高的
        deduped_docs = self._deduplicate(reranked_docs)

        max_chars = int(self._max_context_tokens * APPROX_CHARS_PER_TOKEN)  # tokens * chars/token = chars
        header = "[参考资料]\n"
        parts: list[str] = [header]
        current_chars = len(header)

        for idx, doc in enumerate(deduped_docs, start=1):
            meta = doc.metadata or {}
            title = meta.get("title", "未知文档")
            section = meta.get("section", "未知章节")
            author = meta.get("author", "未知")
            date = meta.get("date", "未知")

            source_line = (
                f"[来源{idx}] 文档标题：{title} | 章节：{section} "
                f"| 作者：{author} | 日期：{date}\n"
            )
            content_line = f"内容：{doc.content}\n"

            block = source_line + content_line
            block_chars = len(block)

            if current_chars + block_chars > max_chars:
                logger.info(
                    "context truncated at source %d/%d (chars=%d, max=%d)",
                    idx,
                    len(deduped_docs),
                    current_chars,
                    max_chars,
                )
                break

            parts.append(block)
            current_chars += block_chars

        context = "\n".join(parts)
        logger.info("built context with %d sources, %d chars", len(parts) - 1, len(context))
        return context

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """计算两段文本的字符级 Jaccard 相似度。"""
        set_a = set(text_a)
        set_b = set(text_b)
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    @classmethod
    def _deduplicate(
        cls, docs: list[SearchResult], threshold: float = 0.8
    ) -> list[SearchResult]:
        """基于内容的 Jaccard 相似度去重，保留排名更高的文档。"""
        kept: list[SearchResult] = []
        for doc in docs:
            is_duplicate = False
            for existing in kept:
                if cls._jaccard_similarity(doc.content, existing.content) > threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(doc)
        removed = len(docs) - len(kept)
        if removed > 0:
            logger.info("deduplicated context: removed %d/%d docs", removed, len(docs))
        return kept

    def estimate_tokens(self, text: str) -> int:
        """粗略估算文本的 token 数（中文约 1.5 字符/token）。"""
        return int(len(text) / 1.5)

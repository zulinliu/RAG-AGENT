from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    project_id: str
    content: str
    title: str
    section: str | None = None
    author: str | None = None
    date: str | None = None
    relevance_score: float = 0.0
    chunk_type: str = "paragraph"
    hierarchy: list[str] = Field(default_factory=list)


class ContextBuilder:
    def __init__(self, max_context_tokens: int = 6000):
        self.max_context_tokens = max_context_tokens

    def build_context(self, chunks: list[RetrievedChunk]) -> tuple[str, dict[str, dict[str, Any]]]:
        sorted_chunks = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
        source_mapping: dict[str, dict[str, Any]] = {}
        parts: list[str] = []
        current_tokens = 0
        header = "【参考资料】\n"
        current_tokens += self._estimate_tokens(header)

        for idx, chunk in enumerate(sorted_chunks, start=1):
            source_id = str(idx)
            meta_parts = [f"文档标题：{chunk.title}"]
            if chunk.section:
                meta_parts.append(f"章节：{chunk.section}")
            if chunk.author:
                meta_parts.append(f"作者：{chunk.author}")
            if chunk.date:
                meta_parts.append(f"日期：{chunk.date}")
            meta_str = " | ".join(meta_parts)

            block = f"[来源{source_id}] {meta_str}\n内容：{chunk.content}\n\n"
            block_tokens = self._estimate_tokens(block)

            if current_tokens + block_tokens > self.max_context_tokens and parts:
                break

            parts.append(block)
            current_tokens += block_tokens
            source_mapping[source_id] = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "project_id": chunk.project_id,
                "title": chunk.title,
                "section": chunk.section,
                "author": chunk.author,
                "date": chunk.date,
                "relevance_score": chunk.relevance_score,
                "chunk_type": chunk.chunk_type,
                "hierarchy": chunk.hierarchy,
                "content": chunk.content,
            }

        context = header + "".join(parts)
        return context, source_mapping

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        char_count = 0
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                char_count += 2
            else:
                char_count += 1
        return char_count

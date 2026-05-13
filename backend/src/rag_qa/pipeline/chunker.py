from __future__ import annotations

import uuid

import jieba  # type: ignore[import-untyped]
from pydantic import BaseModel

from rag_qa.schemas.metadata import ChunkType, DocumentSection, ParsedDocument


class ChunkStrategy(BaseModel):
    target_size: int = 800
    max_size: int = 1500
    min_size: int = 100
    overlap: int = 150
    separators: list[str] = ["\n\n", "\n", "。", "！", "？", "；", "，", " "]


TECHNICAL_DOC = ChunkStrategy(target_size=1200, max_size=1500, overlap=200)
DESIGN_DOC = ChunkStrategy(target_size=800, max_size=1200, overlap=150)
MEETING_MINUTES = ChunkStrategy(target_size=600, max_size=1000, overlap=100)
TABLE = ChunkStrategy(target_size=2000, max_size=3000, overlap=0)
FAQ = ChunkStrategy(target_size=500, max_size=1000, overlap=0)


class ChunkResult(BaseModel):
    chunk_id: str
    content: str
    chunk_type: ChunkType
    parent_title: str | None = None
    hierarchy: list[str] = []
    char_count: int
    token_count: int | None = None


class ChineseChunker:
    def __init__(self, strategy: ChunkStrategy | None = None):
        self.strategy = strategy or DESIGN_DOC

    def chunk_document(self, parsed_doc: ParsedDocument) -> list[ChunkResult]:
        if parsed_doc.sections:
            raw_blocks = self._split_by_structure(parsed_doc.sections)
        else:
            raw_blocks = [(parsed_doc.content, None, [], ChunkType.PARAGRAPH)]

        all_chunks: list[str] = []
        chunk_meta: list[tuple[str | None, list[str], ChunkType]] = []

        for content, parent_title, hierarchy, chunk_type in raw_blocks:
            if len(content) > self.strategy.max_size:
                sub_chunks = self._recursive_split(
                    content, self.strategy.separators, self.strategy.max_size
                )
                for sc in sub_chunks:
                    all_chunks.append(sc)
                    chunk_meta.append((parent_title, hierarchy, chunk_type))
            else:
                all_chunks.append(content)
                chunk_meta.append((parent_title, hierarchy, chunk_type))

        if self.strategy.overlap > 0:
            all_chunks = self._add_overlap(all_chunks, self.strategy.overlap)

        results: list[ChunkResult] = []
        for i, chunk_text in enumerate(all_chunks):
            chunk_text = self._check_semantic_boundary(chunk_text)
            char_count = len(chunk_text)

            if char_count < self.strategy.min_size and results:
                results[-1].content += chunk_text
                results[-1].char_count = len(results[-1].content)
                results[-1].token_count = int(results[-1].char_count / 1.5)
                continue

            parent_title, hierarchy, chunk_type = chunk_meta[i]
            results.append(
                ChunkResult(
                    chunk_id=str(uuid.uuid4()),
                    content=chunk_text,
                    chunk_type=chunk_type,
                    parent_title=parent_title,
                    hierarchy=hierarchy,
                    char_count=char_count,
                    token_count=int(char_count / 1.5),
                )
            )

        return results

    def _split_by_structure(
        self, sections: list[DocumentSection]
    ) -> list[tuple[str, str | None, list[str], ChunkType]]:
        blocks: list[tuple[str, str | None, list[str], ChunkType]] = []
        self._collect_blocks(sections, [], blocks)
        return blocks

    def _collect_blocks(
        self,
        sections: list[DocumentSection],
        parent_hierarchy: list[str],
        blocks: list[tuple[str, str | None, list[str], ChunkType]],
    ) -> None:
        for section in sections:
            hierarchy = parent_hierarchy + [section.title]
            parts: list[str] = []
            if section.title:
                parts.append(section.title)
            if section.content:
                parts.append(section.content)

            if parts:
                combined = "\n\n".join(parts)
                blocks.append((combined, section.title, hierarchy, section.chunk_type))

            if section.children:
                self._collect_blocks(section.children, hierarchy, blocks)

    def _recursive_split(
        self, text: str, separators: list[str], max_size: int
    ) -> list[str]:
        if len(text) <= max_size:
            return [text]

        if not separators:
            return [text[i : i + max_size] for i in range(0, len(text), max_size)]

        sep = separators[0]
        remaining_seps = separators[1:]

        parts = text.split(sep)

        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= max_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > max_size:
                    sub = self._recursive_split(part, remaining_seps, max_size)
                    chunks.extend(sub)
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        return chunks

    def _check_semantic_boundary(self, text: str) -> str:
        if not text:
            return text

        words = list(jieba.cut(text))
        if not words:
            return text

        pos = 0
        word_ends: list[int] = []
        for word in words:
            idx = text.find(word, pos)
            if idx == -1:
                break
            word_ends.append(idx + len(word))
            pos = idx + len(word)

        if not word_ends or word_ends[-1] == len(text):
            return text

        for end in reversed(word_ends):
            if end < len(text):
                result = text[:end].rstrip()
                return result if result else text

        return text

    def _add_overlap(self, chunks: list[str], overlap: int) -> list[str]:
        if overlap <= 0 or len(chunks) <= 1:
            return chunks

        result: list[str] = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev = chunks[i - 1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                chunk = overlap_text + chunk
            result.append(chunk)

        return result

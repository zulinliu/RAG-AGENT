from __future__ import annotations

import os

from rag_qa.pipeline.parser_base import BaseParser, ParsedDocument, ParsedSection
from rag_qa.schemas.metadata import ChunkType


class TextParser(BaseParser):

    async def parse(self, file_path: str) -> ParsedDocument:
        file_size, mime_type = self._get_file_info(file_path)
        checksum = self._compute_checksum(file_path)

        content = self._read_file(file_path)

        title = os.path.splitext(os.path.basename(file_path))[0]
        sections: list[ParsedSection] = []

        paragraphs = content.split("\n\n")
        for idx, para in enumerate(paragraphs):
            text = para.strip()
            if not text:
                continue
            text = "\n".join(line.strip() for line in text.split("\n"))
            sections.append(
                ParsedSection(
                    level=0,
                    title=f"段落 {idx + 1}" if len(paragraphs) > 1 else "",
                    content=text,
                    chunk_type=ChunkType.PARAGRAPH,
                )
            )

        if not sections and content.strip():
            sections.append(
                ParsedSection(
                    level=0,
                    title="",
                    content=content.strip(),
                    chunk_type=ChunkType.PARAGRAPH,
                )
            )

        return ParsedDocument(
            title=title,
            author=None,
            sections=sections,
            metadata={},
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
        )

    def _read_file(self, file_path: str) -> str:
        encodings = ["utf-8", "gbk", "gb2312", "gb18030"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

from __future__ import annotations

import os
import re

from rag_qa.pipeline.parser_base import BaseParser, ParsedDocument, ParsedSection
from rag_qa.schemas.metadata import ChunkType


class MarkdownParser(BaseParser):

    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    async def parse(self, file_path: str) -> ParsedDocument:
        file_size, mime_type = self._get_file_info(file_path)
        checksum = self._compute_checksum(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        title = os.path.splitext(os.path.basename(file_path))[0]
        first_heading = self.HEADING_RE.search(content)
        if first_heading:
            title = first_heading.group(2).strip()

        sections: list[ParsedSection] = []
        headings = list(self.HEADING_RE.finditer(content))

        if not headings:
            sections.append(
                ParsedSection(
                    level=1,
                    title=title,
                    content=content.strip(),
                    chunk_type=ChunkType.PARAGRAPH,
                )
            )
        else:
            for idx, match in enumerate(headings):
                level = len(match.group(1))
                heading_title = match.group(2).strip()
                start = match.end()
                end = headings[idx + 1].start() if idx + 1 < len(headings) else len(content)
                section_text = content[start:end].strip()

                code_blocks: list[str] = []
                code_pattern = re.compile(r"```[\s\S]*?```")
                for cm in code_pattern.finditer(section_text):
                    code_blocks.append(cm.group())

                non_code_text = code_pattern.sub("", section_text).strip()

                if non_code_text:
                    sections.append(
                        ParsedSection(
                            level=level,
                            title=heading_title,
                            content=non_code_text,
                            chunk_type=ChunkType.PARAGRAPH,
                        )
                    )

                for code in code_blocks:
                    sections.append(
                        ParsedSection(
                            level=level + 1,
                            title=f"{heading_title} - 代码块",
                            content=code,
                            chunk_type=ChunkType.CODE,
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

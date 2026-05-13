from __future__ import annotations

import os
import re

import fitz

from rag_qa.pipeline.parser_base import BaseParser, ParsedDocument, ParsedSection
from rag_qa.schemas.metadata import ChunkType


class PDFParser(BaseParser):

    async def parse(self, file_path: str) -> ParsedDocument:
        file_size, mime_type = self._get_file_info(file_path)
        checksum = self._compute_checksum(file_path)
        doc = fitz.open(file_path)
        title = os.path.splitext(os.path.basename(file_path))[0]
        author = doc.metadata.get("author") or None
        sections: list[ParsedSection] = []
        total_text_len = 0
        page_texts: list[str] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts.append(text)
            total_text_len += len(text.strip())

        is_scanned = len(doc) > 0 and total_text_len < len(doc) * 50

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_label = f"第 {page_num + 1} 页"

            if is_scanned:
                sections.append(
                    ParsedSection(
                        level=1,
                        title=page_label,
                        content="[OCR待处理]",
                        chunk_type=ChunkType.IMAGE,
                    )
                )
                continue

            text = page_texts[page_num]
            tables = page.find_tables()
            table_regions: list[tuple[float, float, float, float]] = []
            for table in tables:
                table_regions.append(table.bbox)
                md_table = table.to_markdown()
                sections.append(
                    ParsedSection(
                        level=2,
                        title=f"{page_label} - 表格",
                        content=md_table,
                        chunk_type=ChunkType.TABLE,
                    )
                )

            lines = text.split("\n")
            content_lines: list[str] = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                is_in_table = False
                for bbox in table_regions:
                    try:
                        rects = page.search_for(stripped)
                        if rects:
                            rx = (rects[0].x0 + rects[0].x1) / 2
                            ry = (rects[0].y0 + rects[0].y1) / 2
                            if bbox[0] <= rx <= bbox[2] and bbox[1] <= ry <= bbox[3]:
                                is_in_table = True
                                break
                    except Exception:
                        pass
                if not is_in_table:
                    content_lines.append(stripped)

            page_content = "\n".join(content_lines)
            if page_content.strip():
                heading_lines: list[str] = []
                body_lines: list[str] = []
                for cl in content_lines:
                    if re.match(r"^[0-9]+[\.\s]", cl) and len(cl) < 80:
                        heading_lines.append(cl)
                    else:
                        body_lines.append(cl)

                if heading_lines and body_lines:
                    for hl in heading_lines:
                        sections.append(
                            ParsedSection(
                                level=2,
                                title=hl,
                                content="",
                                chunk_type=ChunkType.HEADING,
                            )
                        )
                    sections.append(
                        ParsedSection(
                            level=1,
                            title=page_label,
                            content="\n".join(body_lines),
                            chunk_type=ChunkType.PARAGRAPH,
                        )
                    )
                else:
                    sections.append(
                        ParsedSection(
                            level=1,
                            title=page_label,
                            content=page_content,
                            chunk_type=ChunkType.PARAGRAPH,
                        )
                    )

        page_count = len(doc)
        doc.close()

        return ParsedDocument(
            title=title,
            author=author,
            sections=sections,
            metadata={
                "page_count": page_count,
                "is_scanned": is_scanned,
            },
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
        )

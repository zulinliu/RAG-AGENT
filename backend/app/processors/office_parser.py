"""Office 文档解析器（Word, Excel, PPT）。"""

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parser import BaseParser, DocumentSection, SectionType, register_parser

logger = logging.getLogger(__name__)


# ======================================================================
# Word 解析器
# ======================================================================

class WordParser(BaseParser):
    """Word (.docx) 文档解析器。

    使用 python-docx 提取段落、表格和标题层级。
    """

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析 Word 文档。"""
        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(file_path)
        sections: List[DocumentSection] = []

        # 构建 O(1) 查找表，避免对每个 element 线性扫描
        element_map = {p._element: p for p in doc.paragraphs}
        table_map = {t._element: t for t in doc.tables}

        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                # 段落
                para = element_map.get(element)
                if para is None:
                    continue

                text = para.text.strip()
                if not text:
                    continue

                style_name = (para.style.name or "").lower() if para.style else ""
                heading_level = self._get_heading_level(style_name)

                if heading_level > 0:
                    sections.append(DocumentSection(
                        title=text,
                        content="",
                        section_type=SectionType.HEADING,
                        level=heading_level,
                    ))
                else:
                    # 检测是否为列表项
                    is_list = self._is_list_item(para)
                    sections.append(DocumentSection(
                        title="",
                        content=text,
                        section_type=SectionType.LIST if is_list else SectionType.PARAGRAPH,
                        level=0,
                    ))

            elif tag == "tbl":
                # 表格
                table = table_map.get(element)
                if table is None:
                    continue
                md = self._table_to_markdown(table)
                if md:
                    sections.append(DocumentSection(
                        title="",
                        content=md,
                        section_type=SectionType.TABLE,
                        level=0,
                    ))

        return sections

    def supported_mimes(self) -> List[str]:
        return [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

    @staticmethod
    def _get_heading_level(style_name: str) -> int:
        """从样式名获取标题级别。"""
        mapping = {
            "heading 1": 1, "heading1": 1, "标题 1": 1,
            "heading 2": 2, "heading2": 2, "标题 2": 2,
            "heading 3": 3, "heading3": 3, "标题 3": 3,
            "heading 4": 4, "heading4": 4, "标题 4": 4,
            "heading 5": 5, "heading5": 5, "标题 5": 5,
            "heading 6": 6, "heading6": 6, "标题 6": 6,
        }
        return mapping.get(style_name, 0)

    @staticmethod
    def _is_list_item(paragraph: Any) -> bool:
        """判断段落是否为列表项。"""
        style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
        return "list" in style_name or "列表" in style_name

    @staticmethod
    def _table_to_markdown(table: Any) -> str:
        """将 Word 表格转为 Markdown，处理合并单元格。"""
        rows: List[List[str]] = []
        prev_cells: List[str] = []

        for row_idx, row in enumerate(table.rows):
            cells: List[str] = []
            for cell in row.cells:
                text = cell.text.strip().replace("\n", " ")
                # 检测合并单元格：通过 gridSpan XML 属性判断
                tc = cell._tc  # type: ignore[attr-defined]
                grid_span_elem = tc.find(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}gridSpan"
                )
                if grid_span_elem is not None:
                    span_val = grid_span_elem.get(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val",
                        "1",
                    )
                    span_count = int(span_val)
                    # 对合并的额外列用 [merged] 标记
                    cells.append(text)
                    for _ in range(span_count - 1):
                        cells.append("[merged]")
                else:
                    cells.append(text)

            # 对纵向合并：检查相邻行单元格文本是否完全相同
            if row_idx > 0 and cells and cells == prev_cells:
                cells = [c if c == "[merged]" else "[merged]" for c in cells]

            rows.append(cells)
            prev_cells = list(cells)

        if not rows:
            return ""

        max_cols = max(len(r) for r in rows)
        lines: List[str] = []
        for i, row in enumerate(rows):
            padded = row + [""] * (max_cols - len(row))
            lines.append("| " + " | ".join(padded) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(lines)


# ======================================================================
# Excel 解析器
# ======================================================================

class ExcelParser(BaseParser):
    """Excel (.xlsx) 文档解析器。

    使用 openpyxl/pandas 将每个 sheet 转为 Markdown 表格。
    """

    # 大表格按此行数切分
    CHUNK_ROW_LIMIT = 100

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析 Excel 文档。"""
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sections: List[DocumentSection] = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            # 每个 sheet 作为一个标题
            sections.append(DocumentSection(
                title=sheet_name,
                content="",
                section_type=SectionType.HEADING,
                level=1,
                metadata={"sheet_name": sheet_name},
            ))

            # 提取数据行
            rows: List[List[str]] = []
            for row in ws.iter_rows(values_only=True):
                cells = [str(cell) if cell is not None else "" for cell in row]
                # 跳过全空行
                if any(c.strip() for c in cells):
                    rows.append(cells)

            if rows:
                # 大表格按行数切分，保留表头
                if len(rows) > self.CHUNK_ROW_LIMIT:
                    header = rows[0]
                    for chunk_start in range(1, len(rows), self.CHUNK_ROW_LIMIT):
                        chunk_rows = [header] + rows[chunk_start:chunk_start + self.CHUNK_ROW_LIMIT]
                        md = self._rows_to_markdown(chunk_rows)
                        chunk_index = (chunk_start - 1) // self.CHUNK_ROW_LIMIT
                        sections.append(DocumentSection(
                            title="",
                            content=md,
                            section_type=SectionType.TABLE,
                            level=0,
                            metadata={
                                "sheet_name": sheet_name,
                                "row_count": len(chunk_rows) - 1,
                                "chunk_index": chunk_index,
                            },
                        ))
                else:
                    md = self._rows_to_markdown(rows)
                    sections.append(DocumentSection(
                        title="",
                        content=md,
                        section_type=SectionType.TABLE,
                        level=0,
                        metadata={"sheet_name": sheet_name, "row_count": len(rows)},
                    ))

        wb.close()
        return sections

    def supported_mimes(self) -> List[str]:
        return [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]

    @staticmethod
    def _rows_to_markdown(rows: List[List[str]]) -> str:
        """将行数据转为 Markdown 表格。"""
        if not rows:
            return ""

        max_cols = max(len(r) for r in rows)
        lines: List[str] = []
        for i, row in enumerate(rows):
            padded = row + [""] * (max_cols - len(row))
            lines.append("| " + " | ".join(padded) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(lines)


# ======================================================================
# PPT 解析器
# ======================================================================

class PPTParser(BaseParser):
    """PowerPoint (.pptx) 文档解析器。

    使用 python-pptx 提取文本框和备注。
    """

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析 PPT 文档。"""
        from pptx import Presentation

        prs = Presentation(file_path)
        sections: List[DocumentSection] = []

        for slide_idx, slide in enumerate(prs.slides):
            # 每页幻灯片作为一个标题
            title_text = self._get_slide_title(slide)
            sections.append(DocumentSection(
                title=f"幻灯片 {slide_idx + 1}" + (f": {title_text}" if title_text else ""),
                content="",
                section_type=SectionType.HEADING,
                level=1,
                metadata={"slide_index": slide_idx},
            ))

            # 提取文本框内容
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if text:
                        sections.append(DocumentSection(
                            title="",
                            content=text,
                            section_type=SectionType.PARAGRAPH,
                            level=0,
                            metadata={"slide_index": slide_idx, "shape_name": shape.name},
                        ))

                # 提取表格
                if shape.has_table:
                    md = self._table_to_markdown(shape.table)
                    if md:
                        sections.append(DocumentSection(
                            title="",
                            content=md,
                            section_type=SectionType.TABLE,
                            level=0,
                            metadata={"slide_index": slide_idx},
                        ))

            # 提取备注
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    sections.append(DocumentSection(
                        title="备注",
                        content=notes,
                        section_type=SectionType.PARAGRAPH,
                        level=0,
                        metadata={"slide_index": slide_idx, "is_notes": True},
                    ))

        return sections

    def supported_mimes(self) -> List[str]:
        return [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ]

    @staticmethod
    def _get_slide_title(slide: Any) -> str:
        """获取幻灯片标题。"""
        for shape in slide.shapes:
            if shape.has_text_frame:
                # 通常标题是第一个文本框
                text = shape.text_frame.text.strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _table_to_markdown(table: Any) -> str:
        """将 PPT 表格转为 Markdown。"""
        rows: List[List[str]] = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows.append(cells)

        if not rows:
            return ""

        max_cols = max(len(r) for r in rows)
        lines: List[str] = []
        for i, row in enumerate(rows):
            padded = row + [""] * (max_cols - len(row))
            lines.append("| " + " | ".join(padded) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(lines)


# 注册所有解析器
register_parser(WordParser())
register_parser(ExcelParser())
register_parser(PPTParser())

"""PDF 文档解析器。

使用 MinerU (magic-pdf) 解析原生 PDF，使用 PaddleOCR 处理扫描件。
"""

import io
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from .parser import BaseParser, DocumentSection, SectionType, register_parser

logger = logging.getLogger(__name__)

# MIME 类型映射
PDF_MIMES = [
    "application/pdf",
]

# 判断扫描件的阈值：如果提取的文本字符数少于此比例，认为是扫描件
SCAN_TEXT_RATIO_THRESHOLD = 0.01


class PDFParser(BaseParser):
    """PDF 文档解析器。

    优先使用 MinerU (magic-pdf) 解析原生 PDF；
    当检测到扫描件时，回退到 PaddleOCR 进行 OCR 识别。
    保留表格结构和标题层级。
    """

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析 PDF 文档。"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        logger.info("开始解析 PDF: %s", file_path)

        # 先尝试用 MinerU 提取
        sections = self._parse_with_mineru(file_path)
        if sections and self._has_enough_text(sections):
            return sections

        # 文本量不足，判断为扫描件，使用 OCR
        logger.info("检测为扫描件，切换到 PaddleOCR: %s", file_path)
        ocr_sections = self._parse_with_ocr(file_path)
        if ocr_sections:
            return ocr_sections

        return sections

    def supported_mimes(self) -> List[str]:
        """返回支持的 MIME 类型。"""
        return PDF_MIMES

    # ------------------------------------------------------------------
    # MinerU 解析
    # ------------------------------------------------------------------

    def _parse_with_mineru(self, file_path: str) -> List[DocumentSection]:
        """使用 MinerU (magic-pdf) 解析 PDF。"""
        try:
            from magic_pdf.data.data_reader_writer import FileBasedDataWriter
            from magic_pdf.data.dataset import PymuDocDataset
        except ImportError:
            logger.warning("MinerU (magic-pdf) 未安装，尝试 PyMuPDF 回退")
            return self._parse_with_pymupdf(file_path)

        sections: List[DocumentSection] = []

        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            ds = PymuDocDataset(pdf_bytes)
            if ds.classify() == "ocr":
                # MinerU 判定为 OCR 类型，交给 PaddleOCR 处理
                return []

            # 使用 MinerU 提取文本内容
            with tempfile.TemporaryDirectory() as tmp_dir:
                writer = FileBasedDataWriter(tmp_dir)
                result = ds.apply_ocr if ds.classify() == "ocr" else ds.apply
                content_list = result()

                for idx, item in enumerate(content_list):
                    section = self._convert_mineru_item(item, idx)
                    if section is not None:
                        sections.append(section)
        except Exception as e:
            logger.error("MinerU 解析失败: %s", e)
            return self._parse_with_pymupdf(file_path)

        return sections

    @staticmethod
    def _convert_mineru_item(item: Any, index: int) -> Optional[DocumentSection]:
        """将 MinerU 输出转换为 DocumentSection。"""
        if not hasattr(item, "type"):
            return None

        item_type = getattr(item, "type", "")
        text = getattr(item, "text", "") or getattr(item, "content", "")

        if item_type in ("text",):
            return DocumentSection(
                title="",
                content=str(text),
                section_type=SectionType.PARAGRAPH,
                level=0,
                metadata={"page_index": index},
            )
        elif item_type in ("table",):
            return DocumentSection(
                title="",
                content=str(text),
                section_type=SectionType.TABLE,
                level=0,
                metadata={"page_index": index},
            )
        elif item_type in ("title",):
            level = getattr(item, "level", 1) or 1
            return DocumentSection(
                title=str(text),
                content="",
                section_type=SectionType.HEADING,
                level=level,
                metadata={"page_index": index},
            )
        elif item_type in ("image",):
            return DocumentSection(
                title="",
                content=str(text) if text else "[图片]",
                section_type=SectionType.IMAGE,
                level=0,
                metadata={"page_index": index},
            )
        return None

    # ------------------------------------------------------------------
    # PaddleOCR 解析
    # ------------------------------------------------------------------

    def _parse_with_ocr(self, file_path: str) -> List[DocumentSection]:
        """使用 PaddleOCR 处理扫描件 PDF。"""
        try:
            from paddleocr import PPStructure
        except ImportError:
            logger.warning("PaddleOCR 未安装，无法处理扫描件")
            return []

        sections: List[DocumentSection] = []
        try:
            table_engine = PPStructure(show_log=False, image_dir=None)

            # 使用 PyMuPDF 将 PDF 页面转为图像
            images = self._pdf_to_images(file_path)

            for page_idx, img in enumerate(images):
                import numpy as np

                if isinstance(img, bytes):
                    import cv2
                    nparr = np.frombuffer(img, np.uint8)
                    img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                else:
                    img_array = np.array(img)

                result = table_engine(img_array)

                for item in result:
                    item_type = item.get("type", "")
                    content = item.get("res", [])

                    if item_type == "title":
                        text = self._extract_ocr_text(content)
                        sections.append(DocumentSection(
                            title=text,
                            content="",
                            section_type=SectionType.HEADING,
                            level=1,
                            metadata={"page_index": page_idx},
                        ))
                    elif item_type == "table":
                        html = item.get("res", {}).get("html", "")
                        md_table = self._html_table_to_markdown(html)
                        sections.append(DocumentSection(
                            title="",
                            content=md_table,
                            section_type=SectionType.TABLE,
                            level=0,
                            metadata={"page_index": page_idx},
                        ))
                    elif item_type == "text":
                        text = self._extract_ocr_text(content)
                        sections.append(DocumentSection(
                            title="",
                            content=text,
                            section_type=SectionType.PARAGRAPH,
                            level=0,
                            metadata={"page_index": page_idx},
                        ))
        except Exception as e:
            logger.error("PaddleOCR 解析失败: %s", e)

        return sections

    @staticmethod
    def _pdf_to_images(file_path: str) -> List[bytes]:
        """将 PDF 页面转为 PNG 图像字节列表。"""
        images: List[bytes] = []
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                images.append(pix.tobytes("png"))
            doc.close()
        except ImportError:
            logger.warning("PyMuPDF 未安装，无法将 PDF 转为图像")
        return images

    @staticmethod
    def _extract_ocr_text(content: Any) -> str:
        """从 OCR 结果中提取文本。"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    texts.append(item.get("text", ""))
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)
        return str(content)

    @staticmethod
    def _html_table_to_markdown(html: str) -> str:
        """将 HTML 表格转为 Markdown 格式。"""
        import re

        if not html:
            return ""

        rows: List[List[str]] = []
        for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
            cells = []
            for td_match in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>", tr_match.group(1), re.DOTALL):
                cell_text = re.sub(r"<[^>]+>", "", td_match.group(1)).strip()
                cells.append(cell_text)
            if cells:
                rows.append(cells)

        if not rows:
            return html

        # 构建 Markdown 表格
        max_cols = max(len(r) for r in rows)
        lines: List[str] = []
        for i, row in enumerate(rows):
            # 补齐列数
            padded = row + [""] * (max_cols - len(row))
            lines.append("| " + " | ".join(padded) + " |")
            if i == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # PyMuPDF 回退
    # ------------------------------------------------------------------

    def _parse_with_pymupdf(self, file_path: str) -> List[DocumentSection]:
        """使用 PyMuPDF (fitz) 回退解析。"""
        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF 未安装，无法解析 PDF")
            return []

        sections: List[DocumentSection] = []
        doc = fitz.open(file_path)

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            # 提取文本块
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block["type"] == 0:  # 文本块
                    text_lines = []
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text_lines.append(span.get("text", ""))
                    text = "\n".join(text_lines).strip()
                    if text:
                        # 检测标题
                        is_heading, level = self._detect_heading(block)
                        sections.append(DocumentSection(
                            title=text if is_heading else "",
                            content="" if is_heading else text,
                            section_type=SectionType.HEADING if is_heading else SectionType.PARAGRAPH,
                            level=level,
                            metadata={"page_index": page_idx},
                        ))

        doc.close()
        return sections

    @staticmethod
    def _detect_heading(block: Dict) -> tuple:
        """检测文本块是否为标题。"""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 12)
                flags = span.get("flags", 0)
                is_bold = bool(flags & 2**4)
                # 大于 16pt 或粗体且大于 13pt 判定为标题
                if size >= 18:
                    return True, 1
                if size >= 15 and is_bold:
                    return True, 2
                if size >= 13 and is_bold:
                    return True, 3
        return False, 0

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _has_enough_text(sections: List[DocumentSection]) -> bool:
        """判断解析结果中是否有足够的文本内容。"""
        total_chars = sum(len(s.content) for s in sections)
        return total_chars > 100


# 注册解析器
register_parser(PDFParser())

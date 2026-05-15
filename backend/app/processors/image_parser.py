"""图片 OCR 解析器 — 使用 PaddleOCR 提取图片中的文字。"""

import logging
from typing import List

from .parser import BaseParser, DocumentSection, SectionType

logger = logging.getLogger(__name__)


class ImageParser(BaseParser):
    """图片 OCR 解析器。"""

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析图片文件，提取 OCR 文字。"""
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            logger.error("文件不存在: %s", file_path)
            return []

        try:
            text = self._ocr_extract(file_path)
        except Exception as e:
            logger.error("OCR 解析失败: %s - %s", file_path, e)
            return []

        if not text.strip():
            logger.info("图片中未检测到文字: %s", file_path)
            return []

        return [
            DocumentSection(
                title="",
                content=text.strip(),
                section_type=SectionType.PARAGRAPH,
                level=0,
                metadata={"source_file": str(path.name), "parser": "image_ocr"},
            )
        ]

    def supported_mimes(self) -> List[str]:
        """返回支持的图片 MIME 类型。"""
        return [
            "image/png",
            "image/jpeg",
            "image/bmp",
            "image/tiff",
            "image/webp",
        ]

    def _ocr_extract(self, file_path: str) -> str:
        """使用 PaddleOCR 提取文字。"""
        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(file_path, cls=True)
            if not result or not result[0]:
                return ""
            lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    lines.append(text)
            return "\n".join(lines)
        except ImportError:
            logger.warning("PaddleOCR 未安装，尝试使用 Tesseract 作为后备")
            return self._tesseract_extract(file_path)

    @staticmethod
    def _tesseract_extract(file_path: str) -> str:
        """使用 Tesseract 作为 OCR 后备方案。"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(file_path)
            return pytesseract.image_to_string(img, lang="chi_sim")
        except ImportError:
            logger.error("PaddleOCR 和 Tesseract 均未安装，无法进行 OCR")
            return ""

"""文本文档解析器（Markdown、纯文本）。"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parser import BaseParser, DocumentSection, SectionType, register_parser

logger = logging.getLogger(__name__)


# ======================================================================
# Markdown 解析器
# ======================================================================

class MarkdownParser(BaseParser):
    """Markdown 文档解析器。

    解析标题层级(H1-H6)、代码块、列表、表格。
    """

    # Markdown 标题正则
    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
    # 代码块围栏
    CODE_FENCE_RE = re.compile(r"^```(\w*)$")
    # 表格行
    TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
    TABLE_SEP_RE = re.compile(r"^\|[\s\-:]+\|$")
    # 列表项
    LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.+)$")

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析 Markdown 文档。"""
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        sections: List[DocumentSection] = []
        current_block: List[str] = []
        current_type = SectionType.PARAGRAPH
        in_code_block = False
        code_lang = ""

        for line in lines:
            stripped = line.rstrip("\n")

            # 代码块处理
            fence_match = self.CODE_FENCE_RE.match(stripped)
            if fence_match:
                if in_code_block:
                    # 结束代码块
                    sections.append(DocumentSection(
                        title=f"Code ({code_lang})" if code_lang else "Code",
                        content="\n".join(current_block),
                        section_type=SectionType.CODE,
                        level=0,
                        metadata={"language": code_lang},
                    ))
                    current_block = []
                    in_code_block = False
                else:
                    # 保存之前的块
                    self._flush_block(current_block, current_type, sections)
                    current_block = []
                    in_code_block = True
                    code_lang = fence_match.group(1)
                    current_type = SectionType.CODE
                continue

            if in_code_block:
                current_block.append(stripped)
                continue

            # 标题
            heading_match = self.HEADING_RE.match(stripped)
            if heading_match:
                self._flush_block(current_block, current_type, sections)
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                sections.append(DocumentSection(
                    title=title,
                    content="",
                    section_type=SectionType.HEADING,
                    level=level,
                ))
                current_block = []
                current_type = SectionType.PARAGRAPH
                continue

            # 表格行
            if self.TABLE_ROW_RE.match(stripped) or self.TABLE_SEP_RE.match(stripped):
                if current_type != SectionType.TABLE:
                    self._flush_block(current_block, current_type, sections)
                    current_block = []
                    current_type = SectionType.TABLE
                current_block.append(stripped)
                continue

            # 列表项
            list_match = self.LIST_RE.match(stripped)
            if list_match:
                if current_type != SectionType.LIST:
                    self._flush_block(current_block, current_type, sections)
                    current_block = []
                    current_type = SectionType.LIST
                current_block.append(list_match.group(3))
                continue

            # 空行
            if not stripped.strip():
                self._flush_block(current_block, current_type, sections)
                current_block = []
                current_type = SectionType.PARAGRAPH
                continue

            # 普通段落
            if current_type != SectionType.PARAGRAPH:
                self._flush_block(current_block, current_type, sections)
                current_block = []
                current_type = SectionType.PARAGRAPH
            current_block.append(stripped)

        # 处理最后的块
        if in_code_block:
            sections.append(DocumentSection(
                title="Code",
                content="\n".join(current_block),
                section_type=SectionType.CODE,
                level=0,
                metadata={"language": code_lang},
            ))
        else:
            self._flush_block(current_block, current_type, sections)

        return sections

    def supported_mimes(self) -> List[str]:
        return ["text/markdown", "text/x-markdown"]

    @staticmethod
    def _flush_block(
        block: List[str],
        block_type: SectionType,
        sections: List[DocumentSection],
    ) -> None:
        """将当前累积的块刷新为段落。"""
        if not block:
            return
        text = "\n".join(block).strip()
        if not text:
            return
        sections.append(DocumentSection(
            title="",
            content=text,
            section_type=block_type,
            level=0,
        ))


# ======================================================================
# 纯文本解析器
# ======================================================================

class PlainTextParser(BaseParser):
    """纯文本解析器。

    按段落分割，自动检测编码。
    """

    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析纯文本文档。"""
        # 尝试多种编码
        content = self._read_with_detection(file_path)
        if content is None:
            return []

        # 按段落分割
        paragraphs = re.split(r"\n\s*\n", content)
        sections: List[DocumentSection] = []

        for para in paragraphs:
            text = para.strip()
            if not text:
                continue
            sections.append(DocumentSection(
                title="",
                content=text,
                section_type=SectionType.PARAGRAPH,
                level=0,
            ))

        return sections

    def supported_mimes(self) -> List[str]:
        return ["text/plain"]

    @staticmethod
    def _read_with_detection(file_path: str) -> Optional[str]:
        """自动检测编码并读取文件。"""
        # 先尝试常见编码
        for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "big5"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        # 使用 chardet 检测
        try:
            import chardet

            with open(file_path, "rb") as f:
                raw = f.read()
            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "utf-8")
            return raw.decode(encoding, errors="replace")
        except ImportError:
            logger.warning("chardet 未安装，无法自动检测编码")
        except Exception as e:
            logger.error("读取文件失败: %s", e)

        return None


# 注册解析器
register_parser(MarkdownParser())
register_parser(PlainTextParser())

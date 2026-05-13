"""中文智能分块引擎。

两阶段分块策略:
1. 结构感知粗分: 按标题层级将文档切分为章节块
2. 递归字符细分: 对超过目标大小的块按中文分隔符递归切分
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .parser import DocumentSection, SectionType

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """文档类型枚举，不同类型使用不同分块参数。"""

    TECHNICAL = "technical"        # 技术文档
    DESIGN = "design"              # 方案/设计文档
    MEETING = "meeting"            # 会议纪要
    TABLE = "table"                # 表格
    DEFAULT = "default"            # 默认


# 文档类型对应的分块参数
CHUNK_CONFIG: Dict[DocumentType, Dict[str, int]] = {
    DocumentType.TECHNICAL: {"chunk_size": 1000, "overlap": 200},
    DocumentType.DESIGN: {"chunk_size": 800, "overlap": 150},
    DocumentType.MEETING: {"chunk_size": 600, "overlap": 100},
    DocumentType.TABLE: {"chunk_size": 0, "overlap": 0},  # 整表为一个块
    DocumentType.DEFAULT: {"chunk_size": 800, "overlap": 150},
}

# 中文分隔符优先级（从高到低）
SEPARATORS = [
    "\n\n",  # 段落
    "\n",    # 换行
    "。",    # 句号
    "！",   # 感叹号
    "？",   # 问号
    "；",   # 分号
    "，",   # 逗号
    " ",    # 空格
]


@dataclass
class Chunk:
    """分块结果。"""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


class ChineseChunker:
    """中文智能分块引擎。

    使用两阶段策略对文档进行智能分块:
    - 第一阶段: 结构感知粗分，按标题层级切分为章节
    - 第二阶段: 递归字符细分，处理超大章节
    """

    def __init__(
        self,
        doc_type: DocumentType = DocumentType.DEFAULT,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> None:
        config = CHUNK_CONFIG.get(doc_type, CHUNK_CONFIG[DocumentType.DEFAULT])
        self.chunk_size = chunk_size or config["chunk_size"]
        self.overlap = overlap or config["overlap"]
        self.doc_type = doc_type

    def chunk(self, sections: List[DocumentSection]) -> List[Chunk]:
        """对解析后的文档段落进行分块。"""
        if not sections:
            return []

        # 阶段一: 结构感知粗分
        coarse_chunks = self._structural_chunking(sections)

        # 阶段二: 递归字符细分
        fine_chunks = self._recursive_refine(coarse_chunks)

        # 添加全局索引
        for idx, chunk in enumerate(fine_chunks):
            chunk.metadata["chunk_index"] = idx

        logger.info(
            "分块完成: %d 个段落 -> %d 个粗块 -> %d 个细块",
            len(sections), len(coarse_chunks), len(fine_chunks),
        )
        return fine_chunks

    # ------------------------------------------------------------------
    # 阶段一: 结构感知粗分
    # ------------------------------------------------------------------

    def _structural_chunking(self, sections: List[DocumentSection]) -> List[Chunk]:
        """按标题层级将文档切分为章节块。"""
        chunks: List[Chunk] = []
        current_title = ""
        current_hierarchy: List[str] = []
        current_parts: List[str] = []
        current_level = 0

        for section in sections:
            if section.section_type == SectionType.HEADING:
                # 保存当前累积的内容
                if current_parts:
                    content = "\n\n".join(current_parts)
                    chunks.append(Chunk(
                        content=content,
                        metadata={
                            "parent_title": current_title,
                            "hierarchy": " > ".join(current_hierarchy) if current_hierarchy else "",
                            "section_type": "section",
                        },
                    ))

                # 开始新章节
                current_title = section.title
                current_level = section.level
                current_parts = []
                # 更新层级路径
                self._update_hierarchy(current_hierarchy, section.title, section.level)

            elif section.section_type == SectionType.TABLE:
                # 表格: 如果是 TABLE 类型，整表为一个块
                if self.doc_type == DocumentType.TABLE:
                    if current_parts:
                        content = "\n\n".join(current_parts)
                        chunks.append(Chunk(
                            content=content,
                            metadata={
                                "parent_title": current_title,
                                "hierarchy": " > ".join(current_hierarchy) if current_hierarchy else "",
                            },
                        ))
                        current_parts = []
                    chunks.append(Chunk(
                        content=section.content,
                        metadata={
                            "parent_title": current_title,
                            "hierarchy": " > ".join(current_hierarchy) if current_hierarchy else "",
                            "section_type": "table",
                        },
                    ))
                else:
                    current_parts.append(section.content)

            else:
                # 普通段落、列表、代码等
                if section.content:
                    current_parts.append(section.content)

        # 处理最后一个块
        if current_parts:
            content = "\n\n".join(current_parts)
            chunks.append(Chunk(
                content=content,
                metadata={
                    "parent_title": current_title,
                    "hierarchy": " > ".join(current_hierarchy) if current_hierarchy else "",
                    "section_type": "section",
                },
            ))

        return chunks

    @staticmethod
    def _update_hierarchy(hierarchy: List[str], title: str, level: int) -> None:
        """更新层级路径。"""
        # 根据标题级别维护层级栈
        while len(hierarchy) >= level:
            if hierarchy:
                hierarchy.pop()
        hierarchy.append(title)

    # ------------------------------------------------------------------
    # 阶段二: 递归字符细分
    # ------------------------------------------------------------------

    def _recursive_refine(self, coarse_chunks: List[Chunk]) -> List[Chunk]:
        """对超过目标大小的块进行递归细分。"""
        if self.chunk_size == 0:
            # chunk_size=0 表示不分块（如表格）
            return coarse_chunks

        result: List[Chunk] = []
        for chunk in coarse_chunks:
            if chunk.char_count <= self.chunk_size:
                result.append(chunk)
            else:
                sub_chunks = self._split_recursive(
                    chunk.content,
                    self.chunk_size,
                    self.overlap,
                    separators=SEPARATORS,
                    metadata=chunk.metadata,
                )
                result.extend(sub_chunks)

        return result

    def _split_recursive(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        separators: List[str],
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
        """递归按分隔符切分文本。"""
        if len(text) <= chunk_size:
            # 检查边界是否截断完整词语
            text = self._fix_word_boundary(text)
            return [Chunk(content=text, metadata={**metadata})]

        if not separators:
            # 没有更多分隔符，强制切分
            return self._force_split(text, chunk_size, overlap, metadata)

        sep = separators[0]
        remaining_seps = separators[1:]

        # 按当前分隔符分割
        parts = text.split(sep)

        chunks: List[Chunk] = []
        current_text = ""

        for i, part in enumerate(parts):
            candidate = current_text + (sep if current_text else "") + part if sep != "\n\n" else (
                current_text + "\n\n" + part
            )

            if len(candidate) <= chunk_size:
                current_text = candidate
            else:
                # 保存当前累积的文本
                if current_text:
                    fixed = self._fix_word_boundary(current_text)
                    chunks.append(Chunk(content=fixed, metadata={**metadata}))

                # 如果单个 part 超过 chunk_size，用下一级分隔符切分
                if len(part) > chunk_size:
                    sub = self._split_recursive(part, chunk_size, overlap, remaining_seps, metadata)
                    chunks.extend(sub)
                    current_text = ""
                else:
                    current_text = part

        if current_text:
            fixed = self._fix_word_boundary(current_text)
            chunks.append(Chunk(content=fixed, metadata={**metadata}))

        # 添加重叠
        if overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks, overlap, metadata)

        return chunks

    def _force_split(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
        """强制按字符数切分。"""
        chunks: List[Chunk] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            # 检查词语边界
            chunk_text = self._fix_word_boundary(chunk_text)
            chunks.append(Chunk(content=chunk_text, metadata={**metadata}))
            start = end - overlap

        return chunks

    @staticmethod
    def _add_overlap(chunks: List[Chunk], overlap: int, metadata: Dict[str, Any]) -> List[Chunk]:
        """为相邻块添加重叠内容。"""
        result: List[Chunk] = []
        for i, chunk in enumerate(chunks):
            content = chunk.content
            if i > 0 and overlap > 0:
                prev_tail = chunks[i - 1].content[-overlap:]
                if not content.startswith(prev_tail):
                    content = prev_tail + content
            if i < len(chunks) - 1 and overlap > 0:
                next_head = chunks[i + 1].content[:overlap]
                if not content.endswith(next_head):
                    content = content + next_head
            result.append(Chunk(content=content, metadata={**chunk.metadata}))
        return result

    @staticmethod
    def _fix_word_boundary(text: str) -> str:
        """使用 jieba 检查并修复词语边界截断。"""
        try:
            import jieba

            if not text:
                return text

            # 检查末尾是否为半个词语
            words = list(jieba.cut(text))
            if len(words) < 2:
                return text

            # 获取最后一个完整词语
            last_word = words[-1].strip()
            if last_word and len(last_word) > 1:
                # 如果最后一个词被截断，移除不完整部分
                tail = text[-len(last_word):]
                if tail != last_word:
                    # 可能被截断了，回退到上一个分隔符位置
                    for sep in SEPARATORS:
                        pos = text[:-1].rfind(sep)
                        if pos > len(text) // 2:
                            return text[: pos + len(sep)]

            return text
        except ImportError:
            # jieba 未安装，不做边界修复
            return text

    @staticmethod
    def detect_document_type(sections: List[DocumentSection]) -> DocumentType:
        """根据内容特征自动检测文档类型。"""
        if not sections:
            return DocumentType.DEFAULT

        # 计算各类型段落的比例
        total = len(sections)
        table_count = sum(1 for s in sections if s.section_type == SectionType.TABLE)
        code_count = sum(1 for s in sections if s.section_type == SectionType.CODE)
        heading_count = sum(1 for s in sections if s.section_type == SectionType.HEADING)

        # 全表格文档
        if total > 0 and table_count / total > 0.7:
            return DocumentType.TABLE

        # 技术文档: 有代码块，标题多
        if code_count > 0 and heading_count > 3:
            return DocumentType.TECHNICAL

        # 会议纪要: 短段落为主，标题少
        avg_len = sum(len(s.content) for s in sections) / max(total, 1)
        if avg_len < 100 and heading_count < 3:
            return DocumentType.MEETING

        # 方案/设计文档: 标题多，段落较长
        if heading_count > 2:
            return DocumentType.DESIGN

        return DocumentType.DEFAULT

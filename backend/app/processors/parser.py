"""文档解析器基类和自动路由。"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SectionType(str, Enum):
    """文档段落类型。"""

    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    CODE = "code"
    IMAGE = "image"
    HEADING = "heading"


@dataclass
class DocumentSection:
    """解析后的文档段落。"""

    title: str
    content: str
    section_type: SectionType
    level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """文档解析器基类。"""

    @abstractmethod
    def parse(self, file_path: str, mime_type: str) -> List[DocumentSection]:
        """解析文档，返回段落列表。"""

    @abstractmethod
    def supported_mimes(self) -> List[str]:
        """返回支持的 MIME 类型列表。"""


# 全局解析器注册表
_parser_registry: Dict[str, BaseParser] = {}


def register_parser(parser: BaseParser) -> None:
    """注册解析器到全局注册表。"""
    for mime in parser.supported_mimes():
        _parser_registry[mime] = parser
    logger.info("已注册解析器: %s -> %s", parser.__class__.__name__, parser.supported_mimes())


def get_parser(mime_type: str) -> Optional[BaseParser]:
    """根据 MIME 类型获取对应的解析器。"""
    parser = _parser_registry.get(mime_type)
    if parser is None:
        # 尝试通配符匹配
        main_type = mime_type.split("/")[0]
        parser = _parser_registry.get(f"{main_type}/*")
    return parser


def auto_parse(file_path: str, mime_type: Optional[str] = None) -> List[DocumentSection]:
    """根据 MIME 类型自动选择解析器并解析文档。"""
    if mime_type is None:
        mime_type = _guess_mime(file_path)

    parser = get_parser(mime_type)
    if parser is None:
        logger.warning("未找到 MIME 类型 %s 对应的解析器: %s", mime_type, file_path)
        return []

    return parser.parse(file_path, mime_type)


def _guess_mime(file_path: str) -> str:
    """猜测文件 MIME 类型。"""
    import mimetypes

    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


# ---------------------------------------------------------------------------
# Built-in parser registrations
# ---------------------------------------------------------------------------

from .image_parser import ImageParser  # noqa: E402

register_parser(ImageParser())

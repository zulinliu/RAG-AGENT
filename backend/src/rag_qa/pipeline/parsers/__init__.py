from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag_qa.pipeline.parser_base import BaseParser

from rag_qa.pipeline.parsers.excel_parser import ExcelParser
from rag_qa.pipeline.parsers.markdown_parser import MarkdownParser
from rag_qa.pipeline.parsers.pdf_parser import PDFParser
from rag_qa.pipeline.parsers.ppt_parser import PPTParser
from rag_qa.pipeline.parsers.text_parser import TextParser
from rag_qa.pipeline.parsers.word_parser import WordParser


class ParserFactory:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseParser]] = {}

    def register(self, file_extension: str, parser_class: type[BaseParser]) -> None:
        self._registry[file_extension.lower()] = parser_class

    def get_parser(self, file_path: str) -> BaseParser | None:
        _, ext = os.path.splitext(file_path)
        parser_class = self._registry.get(ext.lower())
        if parser_class is None:
            return None
        return parser_class()


parser_factory = ParserFactory()

parser_factory.register(".pdf", PDFParser)
parser_factory.register(".docx", WordParser)
parser_factory.register(".doc", WordParser)
parser_factory.register(".xlsx", ExcelParser)
parser_factory.register(".xls", ExcelParser)
parser_factory.register(".pptx", PPTParser)
parser_factory.register(".ppt", PPTParser)
parser_factory.register(".md", MarkdownParser)
parser_factory.register(".markdown", MarkdownParser)
parser_factory.register(".txt", TextParser)
parser_factory.register(".text", TextParser)
parser_factory.register(".log", TextParser)

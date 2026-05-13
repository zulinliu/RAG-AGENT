from __future__ import annotations

import hashlib
import mimetypes
import os
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from rag_qa.schemas.metadata import ChunkType


class ParsedSection(BaseModel):
    level: int
    title: str
    content: str
    chunk_type: ChunkType = ChunkType.PARAGRAPH


class ParsedDocument(BaseModel):
    title: str
    author: str | None = None
    sections: list[ParsedSection] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    file_path: str
    file_size: int
    mime_type: str
    checksum: str


class BaseParser(ABC):

    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        ...

    def _compute_checksum(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_file_info(self, file_path: str) -> tuple[int, str]:
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        return file_size, mime_type

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    DINGTALK = "dingtalk"
    SEAFILE = "seafile"
    NAS = "nas"
    LOCAL = "local"


class ChunkType(StrEnum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    CODE = "code"
    HEADING = "heading"
    IMAGE = "image"


class DocumentSection(BaseModel):
    level: int
    title: str
    content: str
    children: list[DocumentSection] = Field(default_factory=list)
    chunk_type: ChunkType = ChunkType.PARAGRAPH


class DocumentChunkSchema(BaseModel):
    doc_id: str
    source: str
    source_id: str
    project_id: str
    title: str
    chunk_id: str
    content: str
    chunk_type: str = "text"
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    file_path: str
    file_size: int = 0
    mime_type: str | None = None
    checksum: str | None = None
    parent_title: str | None = None
    hierarchy: list[str] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    doc_id: str
    title: str
    author: str | None = None
    content: str
    sections: list[DocumentSection] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    file_path: str
    file_size: int
    mime_type: str
    checksum: str

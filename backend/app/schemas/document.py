"""Pydantic schemas for document-related API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    """Serialized document representation."""

    id: uuid.UUID
    project_id: uuid.UUID
    data_source_id: uuid.UUID | None = None
    title: str
    filename: str | None = None
    file_path: str | None = None
    file_type: str
    file_size: int | None = None
    size: int | None = None
    content_hash: str | None = None
    status: str
    chunk_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkResponse(BaseModel):
    """Serialized document chunk representation."""

    id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatsResponse(BaseModel):
    """Aggregate statistics for documents in a project."""

    total_documents: int = 0
    total_chunks: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_file_type: dict[str, int] = Field(default_factory=dict)


class PaginatedResponse(BaseModel):
    """Generic paginated result wrapper.

    ``items`` is a list of arbitrary response models. Because Pydantic v2
    handles generic models differently, we keep ``items`` as ``list[Any]``
    and let the route handler construct the final response explicitly.
    """

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0

    model_config = {"from_attributes": True}

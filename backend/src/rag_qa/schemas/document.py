from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from rag_qa.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    datasource_id: str | None
    title: str
    file_path: str
    file_size: int
    mime_type: str | None
    checksum: str | None
    chunk_count: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpload(BaseModel):
    datasource_id: str | None = None

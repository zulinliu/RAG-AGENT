"""Document API routes.

Provides document listing, detail, chunk retrieval, deletion,
reprocessing, and local file upload.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import DetailResponse, UploadResponse
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentResponse,
    DocumentStatsResponse,
    PaginatedResponse,
)
from app.services.document_service import DocumentService
from app.utils.auth import (
    PermissionChecker,
    check_project_permission,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/documents
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/documents",
    response_model=PaginatedResponse,
)
async def list_documents(
    project_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
    status_filter: str | None = None,
    source_type: str | None = None,
    file_type: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List documents for a project with optional filters."""
    check_project_permission(current_user, str(project_id))

    svc = DocumentService(db)
    filters: dict[str, Any] = {}
    if status_filter:
        filters["status"] = status_filter
    if source_type:
        filters["source_type"] = source_type
    if file_type:
        filters["file_type"] = file_type

    return await svc.list_documents(
        project_id=project_id,
        page=page,
        size=size,
        filters=filters if filters else None,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{document_id}
# ---------------------------------------------------------------------------


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get document details."""
    svc = DocumentService(db)
    try:
        doc = await svc.get_document(uuid.UUID(document_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(doc.project_id))
    return _document_to_response(doc)


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{document_id}/chunks
# ---------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
async def get_document_chunks(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    """Get all chunks of a document."""
    svc = DocumentService(db)
    try:
        doc = await svc.get_document(uuid.UUID(document_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(doc.project_id))

    chunks = await svc.get_document_chunks(doc.id)
    return [
        DocumentChunkResponse(
            id=c.id,
            document_id=c.document_id,
            project_id=c.project_id,
            chunk_index=c.chunk_index,
            content=c.content,
            token_count=c.char_count,
            metadata=c.metadata_ if isinstance(c.metadata_, dict) else {},
            created_at=c.created_at,
        )
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# DELETE /api/v1/documents/{document_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/documents/{document_id}",
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def delete_document(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DetailResponse:
    """Delete a document and its chunks."""
    svc = DocumentService(db)
    try:
        doc = await svc.get_document(uuid.UUID(document_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(doc.project_id))
    await svc.delete_document(doc.id)
    return DetailResponse(detail="Document deleted")


# ---------------------------------------------------------------------------
# POST /api/v1/documents/{document_id}/reprocess
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/reprocess",
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def reprocess_document(
    document_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DetailResponse:
    """Trigger reprocessing of a document."""
    svc = DocumentService(db)
    try:
        doc = await svc.get_document(uuid.UUID(document_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(doc.project_id))
    await svc.reprocess_document(doc.id)
    return DetailResponse(detail="Document reprocessing triggered")


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/documents/upload
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/documents/upload",
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload a local document file to a project.

    Stores the file in MinIO and creates a document record in pending status.
    """
    from app.config import get_settings

    check_project_permission(current_user, str(project_id))

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Read file content with size limit
    max_size = 100 * 1024 * 1024  # 100 MB
    content = await file.read(max_size + 1)
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {max_size // (1024*1024)}MB)",
        )

    # Validate file type whitelist
    allowed_extensions = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".md", ".txt", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    # Validate content type whitelist
    allowed_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "text/markdown",
        "text/plain",
        "text/csv",
        "application/octet-stream",
    }
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type: {content_type}",
        )

    # Compute content hash for dedup
    content_hash = hashlib.sha256(content).hexdigest()

    # Determine file type from extension
    ext = os.path.splitext(file.filename)[1].lower()
    file_type_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "docx",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".pptx": "pptx",
        ".ppt": "pptx",
        ".md": "markdown",
        ".txt": "text",
        ".csv": "csv",
    }
    file_type = file_type_map.get(ext, "unknown")

    # Sanitize filename strictly
    raw_name = file.filename or "unknown"
    safe_filename = re.sub(r'[^\w\s.\-]', '_', os.path.basename(raw_name))
    if not safe_filename or safe_filename.startswith('.'):
        safe_filename = "unnamed_file"
    storage_dir = Path(os.getenv("UPLOAD_DIR", "/app/uploads")) / str(project_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    local_path = storage_dir / f"{uuid.uuid4()}_{safe_filename}"
    local_path.write_bytes(content)

    object_path = f"{project_id}/{local_path.name}"
    try:
        from app.core.minio_client import get_minio_client

        client = get_minio_client()
        client.ensure_bucket(get_settings().minio.bucket)
        client.put_bytes(
            bucket_name=get_settings().minio.bucket,
            object_name=object_path,
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception:
        logger.info("MinIO unavailable; using local upload path: %s", local_path)

    # Create document record
    from app.models.document import Document

    doc = Document(
        project_id=project_id,
        source_type="local",
        title=file.filename,
        file_path=str(local_path),
        file_size=len(content),
        mime_type=file.content_type,
        file_type=file_type,
        content_hash=content_hash,
        status="pending",
    )
    db.add(doc)
    await db.flush()

    # Trigger async processing
    try:
        from app.tasks.sync_tasks import sync_document_task

        sync_document_task.delay({
            "source": "upload",
            "document_id": str(doc.id),
            "project_id": str(project_id),
            "data_source_id": "",
            "file_path": str(local_path),
            "local_file_path": str(local_path),
            "file_size": len(content),
            "mime_type": content_type,
            "modified_at": datetime.now(timezone.utc).isoformat(),
            "checksum": content_hash,
            "extra": {"object_path": object_path, "filename": file.filename},
        })
    except ImportError:
        logger.warning("Task module not available; document will not be processed automatically")

    return UploadResponse(detail="Document uploaded", document_id=str(doc.id))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/documents/stats
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/documents/stats",
    response_model=DocumentStatsResponse,
)
async def get_document_stats(
    project_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatsResponse:
    """Get aggregate document statistics for a project."""
    check_project_permission(current_user, str(project_id))

    svc = DocumentService(db)
    return await svc.get_document_stats(project_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _document_to_response(doc: Any) -> DocumentResponse:
    """Map an ORM Document to a response schema using model_validate."""
    data = {
        "id": doc.id,
        "project_id": doc.project_id,
        "data_source_id": doc.data_source_id,
        "title": doc.title,
        "filename": doc.title,
        "file_path": doc.file_path,
        "file_type": getattr(doc, "file_type", None) or doc.source_type or "",
        "file_size": doc.file_size,
        "size": doc.file_size,
        "content_hash": doc.content_hash,
        "status": doc.status,
        "chunk_count": 0,
        "metadata": doc.metadata_ if isinstance(doc.metadata_, dict) else {},
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }
    return DocumentResponse.model_validate(data)

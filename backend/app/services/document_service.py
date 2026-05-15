"""Document management service.

Handles document listing, stats, deletion, and reprocessing.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Sequence

from sqlalchemy import delete as sa_delete
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentStatsResponse, PaginatedResponse


class DocumentService:
    """Business logic for document management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_document(self, document_id: uuid.UUID) -> Document:
        """Retrieve a document by ID.

        Raises:
            ValueError: If the document is not found.
        """
        doc = await self._db.get(Document, document_id)
        if doc is None:
            raise ValueError(f"Document not found: {document_id}")
        return doc

    async def list_documents(
        self,
        project_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> PaginatedResponse:
        """Return a paginated list of documents for a project.

        Args:
            project_id: Scope to this project.
            page: 1-based page number.
            size: Page size.
            filters: Optional dict of field-value filters. Supported keys:
                     ``status``, ``source_type``, ``file_type``.

        Returns:
            ``PaginatedResponse`` with document items.
        """
        filters = filters or {}

        base_query = select(Document).where(Document.project_id == project_id)

        # Apply filters
        if "status" in filters:
            base_query = base_query.where(Document.status == filters["status"])
        if "source_type" in filters:
            base_query = base_query.where(Document.source_type == filters["source_type"])
        if "file_type" in filters:
            base_query = base_query.where(Document.file_type == filters["file_type"])

        # Total count
        count_query = select(sa_func.count()).select_from(base_query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated query
        offset = (page - 1) * size
        result = await self._db.execute(
            base_query.order_by(Document.created_at.desc()).offset(offset).limit(size),
        )
        documents = result.scalars().all()
        doc_ids = [doc.id for doc in documents]
        chunk_counts: dict[uuid.UUID, int] = {}
        if doc_ids:
            chunk_count_result = await self._db.execute(
                select(DocumentChunk.document_id, sa_func.count())
                .where(DocumentChunk.document_id.in_(doc_ids))
                .group_by(DocumentChunk.document_id),
            )
            chunk_counts = {row[0]: row[1] for row in chunk_count_result.all()}

        items = []
        for doc in documents:
            item = doc.to_dict()
            item["filename"] = doc.title
            item["size"] = doc.file_size
            item["chunk_count"] = chunk_counts.get(doc.id, 0)
            items.append(item)

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total > 0 else 0,
        )

    async def get_document_chunks(
        self,
        document_id: uuid.UUID,
    ) -> Sequence[DocumentChunk]:
        """Return all chunks belonging to a document.

        Raises:
            ValueError: If the document is not found.
        """
        await self.get_document(document_id)  # ensure existence

        result = await self._db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index),
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_document(self, document_id: uuid.UUID) -> None:
        """Delete a document and all associated chunks.

        Also triggers cleanup in Milvus and Elasticsearch via the
        async task pipeline.

        Raises:
            ValueError: If the document is not found.
        """
        doc = await self.get_document(document_id)

        # Delete chunks
        await self._db.execute(
            sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id),
        )
        # Delete document
        await self._db.delete(doc)
        await self._db.flush()

        # Dispatch async cleanup task for Milvus / ES
        try:
            from app.tasks.sync_tasks import sync_document_task

            sync_document_task.delay({
                "source": "cleanup",
                "file_path": str(document_id),
                "project_id": str(doc.project_id),
                "data_source_id": str(doc.data_source_id) if doc.data_source_id else "",
                "action": "delete",
            })
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Reprocess
    # ------------------------------------------------------------------

    async def reprocess_document(self, document_id: uuid.UUID) -> None:
        """Trigger reprocessing of a document.

        Sets the document status back to ``pending`` and dispatches a
        Celery task to re-parse, re-chunk, and re-index the document.

        Raises:
            ValueError: If the document is not found.
        """
        doc = await self.get_document(document_id)
        doc.status = "pending"
        doc.error_message = None

        # Delete existing chunks so they are regenerated
        await self._db.execute(
            sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id),
        )
        await self._db.flush()

        try:
            from app.tasks.sync_tasks import sync_document_task

            sync_document_task.delay({
                "source": "reprocess",
                "file_path": doc.file_path or "",
                "project_id": str(doc.project_id),
                "data_source_id": str(doc.data_source_id) if doc.data_source_id else "",
                "file_size": doc.file_size,
                "mime_type": doc.mime_type or "",
                "modified_at": doc.updated_at.isoformat() if doc.updated_at else "",
                "action": "reprocess",
            })
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_document_stats(
        self,
        project_id: uuid.UUID,
    ) -> DocumentStatsResponse:
        """Aggregate document statistics for a project."""
        # By status
        status_result = await self._db.execute(
            select(Document.status, sa_func.count())
            .where(Document.project_id == project_id)
            .group_by(Document.status),
        )
        by_status = dict(status_result.all())

        # By file type
        type_result = await self._db.execute(
            select(Document.file_type, sa_func.count())
            .where(Document.project_id == project_id)
            .group_by(Document.file_type),
        )
        by_file_type = dict(type_result.all())

        # Total chunks
        chunk_result = await self._db.execute(
            select(sa_func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.project_id == project_id),
        )
        total_chunks = chunk_result.scalar() or 0

        return DocumentStatsResponse(
            total_documents=sum(by_status.values()),
            total_chunks=total_chunks,
            by_status=by_status,
            by_file_type=by_file_type,
        )

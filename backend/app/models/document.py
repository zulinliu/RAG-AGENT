from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class SyncStatusEnum(str, enum.Enum):
    """Data source sync status."""

    idle = "idle"
    syncing = "syncing"
    completed = "completed"
    failed = "failed"


class ProcessingStatusEnum(str, enum.Enum):
    """Document processing status."""

    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class Document(Base, BaseMixin):
    """A document ingested from a data source."""

    __tablename__ = "documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Normalized file type: pdf / docx / xlsx / pptx / markdown / text / csv / image",
    )
    checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 hex digest of the original file",
    )
    author: Mapped[str | None] = mapped_column(String(256))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        comment="pending / processing / indexed / failed",
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))

    # relationships
    project: Mapped["app.models.project.Project"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        lazy="noload",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base, BaseMixin):
    """A segment of a document produced by the chunking pipeline."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(
        String(32),
        default="paragraph",
        comment="paragraph / table / list / code",
    )
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
    )
    hierarchy: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Ordered list of heading levels, e.g. [{level:1, title:'...'}, ...]",
    )
    parent_title: Mapped[str | None] = mapped_column(String(512))
    vector_id: Mapped[str | None] = mapped_column(
        String(128),
        comment="ID in Milvus collection",
    )
    es_id: Mapped[str | None] = mapped_column(
        String(128),
        comment="Document ID in Elasticsearch",
    )

    # relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")

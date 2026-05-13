from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_qa.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from rag_qa.models.datasource import DataSource


class SyncTaskType(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class SyncTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncTask(Base, TimestampMixin):
    __tablename__ = "sync_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    task_type: Mapped[SyncTaskType] = mapped_column(SAEnum(SyncTaskType), nullable=False)
    status: Mapped[SyncTaskStatus] = mapped_column(
        SAEnum(SyncTaskStatus), default=SyncTaskStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    datasource: Mapped[DataSource] = relationship()

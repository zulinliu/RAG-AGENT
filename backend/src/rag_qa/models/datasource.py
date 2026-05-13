from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_qa.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from rag_qa.models.project import Project


class DataSourceType(StrEnum):
    LOCAL = "local"
    NAS = "nas"
    SEAFILE = "seafile"
    DINGTALK = "dingtalk"


class DataSourceStatus(StrEnum):
    ACTIVE = "active"
    ERROR = "error"
    SYNCING = "syncing"


class DataSource(Base, TimestampMixin):
    __tablename__ = "datasources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[DataSourceType] = mapped_column(SAEnum(DataSourceType), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[DataSourceStatus] = mapped_column(
        SAEnum(DataSourceStatus), default=DataSourceStatus.ACTIVE, nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    project: Mapped[Project] = relationship(back_populates="datasources")

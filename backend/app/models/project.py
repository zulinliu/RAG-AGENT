from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import UserProject


class Project(Base, BaseMixin):
    """A project workspace that groups data sources and knowledge bases."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # relationships
    member_associations: Mapped[list["UserProject"]] = relationship(
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list["DataSource"]] = relationship(
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project",
        lazy="noload",
        cascade="all, delete-orphan",
    )


class DataSource(Base, BaseMixin):
    """An external data source attached to a project."""

    __tablename__ = "data_sources"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="dingtalk / seafile / nas / local",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sync_status: Mapped[str] = mapped_column(
        String(32),
        default="idle",
        comment="idle / syncing / error",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # relationships
    project: Mapped["Project"] = relationship(back_populates="data_sources")

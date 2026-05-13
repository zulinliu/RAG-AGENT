from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import BaseMixin


class Conversation(Base, BaseMixin):
    """A conversation session between a user and the system."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(256))

    # relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, BaseMixin):
    """A single message within a conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="user / assistant",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of source references used to generate this answer",
    )
    feedback: Mapped[str] = mapped_column(
        String(16),
        default="none",
        comment="thumbs_up / thumbs_down / none",
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Model confidence score between 0 and 1",
    )

    # relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

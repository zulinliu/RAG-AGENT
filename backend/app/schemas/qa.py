"""Pydantic schemas for Q&A (question-answering) API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    """Request body for asking a question."""

    question: str = Field(..., min_length=1, max_length=2000)
    project_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    stream: bool = False


class FeedbackRequest(BaseModel):
    """Request body for submitting feedback on an answer."""

    message_id: uuid.UUID
    feedback: str = Field(..., pattern="^(thumbs_up|thumbs_down)$")
    comment: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AskResponse(BaseModel):
    """Response body for a Q&A answer.

    Aligned with the dataclass in app.services.qa_service.AskResponse.
    """

    conversation_id: str
    message_id: str
    query: str
    answer: str
    citations: list[int] = Field(default_factory=list)
    confidence: float = 0.0
    sources_used: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """A single message within a conversation."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str  # "user", "assistant"
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    feedback_rating: int | None = None
    feedback_comment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Serialized conversation representation."""

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

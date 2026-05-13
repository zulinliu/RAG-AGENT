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
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AskResponse(BaseModel):
    """Response body for a Q&A answer."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    question: str
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    model_name: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class StreamChunk(BaseModel):
    """A single chunk in an SSE stream."""

    type: str  # "token", "citation", "done", "error"
    content: str | None = None
    data: dict[str, Any] | None = None


class CitationDetail(BaseModel):
    """Detailed citation information."""

    index: int
    document_id: uuid.UUID
    document_title: str
    chunk_id: uuid.UUID
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


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

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from rag_qa.models.conversation import FeedbackType


class ChatRequest(BaseModel):
    project_id: str
    question: str = Field(..., min_length=1)
    conversation_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: dict | None = None
    confidence_score: float | None = None


class ConversationResponse(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: dict | None = None
    confidence_score: float | None = None
    feedback_type: FeedbackType | None = None
    feedback_comment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType
    comment: str | None = None

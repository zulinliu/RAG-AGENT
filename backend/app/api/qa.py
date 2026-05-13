"""问答 API 路由 — 提供同步问答、流式问答、对话管理和反馈接口。"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/qa", tags=["QA"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    user_id: str
    project_id: str
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None


class AskResponseSchema(BaseModel):
    conversation_id: str
    message_id: str
    query: str
    answer: str
    citations: list[int] = []
    confidence: float = 0.0
    sources_used: list[str] = []
    metadata: dict[str, Any] = {}


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str = Field(..., pattern=r"^(thumbs_up|thumbs_down)$")


class ConversationItem(BaseModel):
    conversation_id: str
    project_id: str
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    conversation_id: str
    project_id: str
    messages: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Dependency injection helper
# ---------------------------------------------------------------------------


def _get_qa_service(request: Request) -> Any:
    """从 app.state 获取 QAService 实例。"""
    service = getattr(request.app.state, "qa_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="QA service not initialized")
    return service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ask", response_model=AskResponseSchema)
async def ask(req: AskRequest, qa_service: Any = Depends(_get_qa_service)) -> Any:
    """同步问答接口。"""
    try:
        result = await qa_service.ask(
            user_id=req.user_id,
            project_id=req.project_id,
            query=req.query,
            conversation_id=req.conversation_id,
        )
        return AskResponseSchema(
            conversation_id=result.conversation_id,
            message_id=result.message_id,
            query=result.query,
            answer=result.answer,
            citations=result.citations,
            confidence=result.confidence,
            sources_used=result.sources_used,
            metadata=result.metadata,
        )
    except Exception:
        logger.exception("ask endpoint failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stream")
async def stream_ask(req: AskRequest, qa_service: Any = Depends(_get_qa_service)) -> StreamingResponse:
    """SSE 流式问答接口。"""

    async def event_generator() -> Any:
        try:
            async for event in qa_service.stream_ask(
                user_id=req.user_id,
                project_id=req.project_id,
                query=req.query,
                conversation_id=req.conversation_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            logger.exception("stream endpoint failed")
            error_event = json.dumps({"type": "error", "data": "Internal server error"})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ConversationItem])
async def list_conversations(
    user_id: str,
    project_id: str | None = None,
    limit: int = 20,
    qa_service: Any = Depends(_get_qa_service),
) -> Any:
    """获取用户对话列表。"""
    try:
        conversations = await qa_service._session.list_conversations(
            user_id=user_id,
            project_id=project_id,
            limit=min(limit, 100),
        )
        return [ConversationItem(**c) for c in conversations]
    except Exception:
        logger.exception("list conversations failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    qa_service: Any = Depends(_get_qa_service),
) -> Any:
    """获取对话详情。"""
    try:
        messages = await qa_service._session.get_history(conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDetail(
            conversation_id=conversation_id,
            project_id="",
            messages=messages,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("get conversation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    qa_service: Any = Depends(_get_qa_service),
) -> dict[str, str]:
    """提交用户反馈 (thumbs_up / thumbs_down)。"""
    try:
        await qa_service.submit_feedback(req.message_id, req.feedback)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("submit feedback failed")
        raise HTTPException(status_code=500, detail="Internal server error")

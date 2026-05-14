"""问答 API 路由 — 提供同步问答、流式问答、对话管理和反馈接口。"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.qa import AskRequest, FeedbackRequest
from app.utils.auth import check_project_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["QA"])


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


@router.post("/ask")
async def ask(
    req: AskRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    qa_service: Any = Depends(_get_qa_service),
) -> Any:
    """同步问答接口。"""
    check_project_permission(current_user, str(req.project_id))
    user_id = current_user["user_id"]

    try:
        result = await qa_service.ask(
            user_id=user_id,
            project_id=str(req.project_id),
            query=req.question,
            conversation_id=str(req.conversation_id) if req.conversation_id else None,
        )
        return result
    except Exception:
        logger.exception("ask endpoint failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stream")
async def stream_ask(
    req: AskRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    qa_service: Any = Depends(_get_qa_service),
) -> StreamingResponse:
    """SSE 流式问答接口。"""
    check_project_permission(current_user, str(req.project_id))
    user_id = current_user["user_id"]

    async def event_generator() -> Any:
        try:
            async for event in qa_service.stream_ask(
                user_id=user_id,
                project_id=str(req.project_id),
                query=req.question,
                conversation_id=str(req.conversation_id) if req.conversation_id else None,
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


@router.get("/conversations")
async def list_conversations(
    project_id: str | None = None,
    limit: int = 20,
    current_user: dict[str, Any] = Depends(get_current_user),
    qa_service: Any = Depends(_get_qa_service),
) -> Any:
    """获取用户对话列表。"""
    user_id = current_user["user_id"]

    if project_id is not None:
        check_project_permission(current_user, project_id)

    try:
        conversations = await qa_service.list_conversations(
            user_id=user_id,
            project_id=project_id,
            limit=min(limit, 100),
        )
        return conversations
    except Exception:
        logger.exception("list conversations failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    qa_service: Any = Depends(_get_qa_service),
) -> Any:
    """获取对话详情。"""
    try:
        messages = await qa_service.get_conversation_history(conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {
            "conversation_id": conversation_id,
            "messages": messages,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("get conversation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    qa_service: Any = Depends(_get_qa_service),
) -> dict[str, str]:
    """提交用户反馈。"""
    try:
        await qa_service.submit_feedback(str(req.message_id), req.feedback)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("submit feedback failed")
        raise HTTPException(status_code=500, detail="Internal server error")

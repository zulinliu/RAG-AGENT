from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.api.deps import get_db, require_role
from rag_qa.models.conversation import FeedbackType, Message
from rag_qa.models.datasource import DataSource
from rag_qa.models.document import Document
from rag_qa.models.project import Project
from rag_qa.models.user import Role, User
from rag_qa.schemas.common import ResponseBase

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=ResponseBase)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN),
):
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    project_count = (await db.execute(select(func.count()).select_from(Project))).scalar() or 0
    document_count = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0
    datasource_count = (await db.execute(select(func.count()).select_from(DataSource))).scalar() or 0
    bad_case_count = (
        await db.execute(
            select(func.count()).select_from(Message).where(Message.feedback_type == FeedbackType.DISLIKE)
        )
    ).scalar() or 0
    return ResponseBase(
        data={
            "user_count": user_count,
            "project_count": project_count,
            "document_count": document_count,
            "datasource_count": datasource_count,
            "bad_case_count": bad_case_count,
        }
    )


@router.get("/sync-tasks", response_model=ResponseBase)
async def list_sync_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN),
):
    result = await db.execute(select(DataSource).order_by(DataSource.updated_at.desc()))
    datasources = result.scalars().all()
    tasks = [
        {
            "id": ds.id,
            "name": ds.name,
            "type": ds.type.value,
            "project_id": ds.project_id,
            "status": ds.status.value,
            "last_synced_at": ds.last_synced_at.isoformat() if ds.last_synced_at else None,
            "sync_interval_minutes": ds.sync_interval_minutes,
        }
        for ds in datasources
    ]
    return ResponseBase(data=tasks)


@router.get("/bad-cases", response_model=ResponseBase)
async def list_bad_cases(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN),
):
    result = await db.execute(
        select(Message).where(Message.feedback_type == FeedbackType.DISLIKE).order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()
    cases = [
        {
            "message_id": m.id,
            "conversation_id": m.conversation_id,
            "content": m.content,
            "feedback_type": m.feedback_type.value if m.feedback_type else None,
            "feedback_comment": m.feedback_comment,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return ResponseBase(data=cases)

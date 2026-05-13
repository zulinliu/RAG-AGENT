from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from rag_qa.models.base import Base, TimestampMixin


class BadCaseCategory(StrEnum):
    RETRIEVAL_ISSUE = "retrieval_issue"
    GENERATION_ISSUE = "generation_issue"


class BadCaseStatus(StrEnum):
    PENDING = "pending"
    CLASSIFIED = "classified"
    RESOLVED = "resolved"


class BadCase(Base, TimestampMixin):
    __tablename__ = "bad_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[BadCaseCategory | None] = mapped_column(SAEnum(BadCaseCategory), nullable=True)
    status: Mapped[BadCaseStatus] = mapped_column(SAEnum(BadCaseStatus), default=BadCaseStatus.PENDING, nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)


class BadCaseManager:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def collect_from_feedback(
        self,
        message_id: str,
        feedback_type: str,
        comment: str | None = None,
    ) -> None:
        stmt = select(BadCase).where(BadCase.message_id == message_id)
        result = await self.db_session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.feedback_type = feedback_type
            existing.comment = comment
        else:
            bad_case = BadCase(
                message_id=message_id,
                feedback_type=feedback_type,
                comment=comment,
                status=BadCaseStatus.PENDING,
            )
            self.db_session.add(bad_case)

        await self.db_session.commit()

    async def classify_badcase(self, badcase_id: str) -> str:
        stmt = select(BadCase).where(BadCase.id == badcase_id)
        result = await self.db_session.execute(stmt)
        bad_case = result.scalar_one_or_none()

        if bad_case is None:
            from rag_qa.core.exceptions import NotFoundException
            raise NotFoundException(f"BadCase {badcase_id} not found")

        if bad_case.comment and any(
            kw in bad_case.comment for kw in ["找不到", "检索不到", "没有相关", "搜不到", "无关文档"]
        ):
            bad_case.category = BadCaseCategory.RETRIEVAL_ISSUE
        else:
            bad_case.category = BadCaseCategory.GENERATION_ISSUE

        bad_case.status = BadCaseStatus.CLASSIFIED
        await self.db_session.commit()

        return bad_case.category.value

    async def list_badcases(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        stmt = (
            select(BadCase)
            .order_by(BadCase.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db_session.execute(stmt)
        bad_cases = result.scalars().all()

        return [
            {
                "id": bc.id,
                "message_id": bc.message_id,
                "feedback_type": bc.feedback_type,
                "comment": bc.comment,
                "category": bc.category.value if bc.category else None,
                "status": bc.status.value,
                "question": bc.question,
                "answer": bc.answer,
                "created_at": bc.created_at.isoformat() if bc.created_at else None,
            }
            for bc in bad_cases
        ]

    async def get_badcase_stats(self) -> dict[str, Any]:
        total_stmt = select(func.count()).select_from(BadCase)
        total_result = await self.db_session.execute(total_stmt)
        total = total_result.scalar() or 0

        category_stmt = select(BadCase.category, func.count()).group_by(BadCase.category)
        category_result = await self.db_session.execute(category_stmt)
        category_counts = {str(cat): cnt for cat, cnt in category_result.all() if cat is not None}

        status_stmt = select(BadCase.status, func.count()).group_by(BadCase.status)
        status_result = await self.db_session.execute(status_stmt)
        status_counts = {str(st): cnt for st, cnt in status_result.all()}

        return {
            "total": total,
            "by_category": category_counts,
            "by_status": status_counts,
        }

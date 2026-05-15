"""RAG 评估和 BadCase 管理 API。"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.utils.auth import check_project_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# --- Schemas ---


class BadCaseCreate(BaseModel):
    """创建 BadCase 记录。"""

    message_id: uuid.UUID
    category: str = Field(..., description="retrieval_problem / generation_problem / other")
    description: str = Field(..., min_length=1, max_length=2000)
    expected_answer: str | None = None


class EvaluationRunRequest(BaseModel):
    """触发评估运行。"""

    project_id: uuid.UUID
    dataset_name: str | None = None


# --- BadCase endpoints ---


@router.post("/bad-cases", response_model=dict)
async def create_bad_case(
    data: BadCaseCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """记录一个 BadCase（用户踩回答触发）。"""
    bad_case_id = str(uuid.uuid4())
    row = await db.execute(
        text(
            """
            SELECT c.project_id, c.user_id
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = :message_id
            """
        ),
        {"message_id": str(data.message_id)},
    )
    owner = row.mappings().first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Message not found")

    check_project_permission(current_user, str(owner["project_id"]))
    if current_user.get("role") != "system_admin" and str(owner["user_id"]) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.execute(
        text(
            """
            INSERT INTO bad_cases (
                id, project_id, message_id, created_by, category,
                description, expected_answer, status
            )
            VALUES (
                :id, :project_id, :message_id, :created_by, :category,
                :description, :expected_answer, 'open'
            )
            """
        ),
        {
            "id": bad_case_id,
            "project_id": str(owner["project_id"]),
            "message_id": str(data.message_id),
            "created_by": current_user["user_id"],
            "category": data.category,
            "description": data.description,
            "expected_answer": data.expected_answer,
        },
    )
    await db.commit()
    logger.info("BadCase created: %s by user %s", bad_case_id, current_user["user_id"])
    return {
        "id": bad_case_id,
        "project_id": str(owner["project_id"]),
        "message_id": str(data.message_id),
        "category": data.category,
        "status": "open",
    }


@router.get("/bad-cases", response_model=list[dict])
async def list_bad_cases(
    project_id: uuid.UUID | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """列出 BadCase 记录。"""
    if project_id is not None:
        check_project_permission(current_user, str(project_id))

    conditions = []
    params: dict[str, Any] = {"limit": size, "offset": (page - 1) * size}
    if current_user.get("role") != "system_admin":
        project_ids = current_user.get("project_ids", [])
        if not project_ids:
            return []
        conditions.append("project_id IN :project_ids")
        params["project_ids"] = project_ids
    if project_id is not None:
        conditions.append("project_id = :project_id")
        params["project_id"] = str(project_id)
    if category:
        conditions.append("category = :category")
        params["category"] = category
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
    stmt = text(
        f"""
            SELECT id, project_id, message_id, category, description,
                   expected_answer, status, created_at, updated_at, resolved_at
            FROM bad_cases
            {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
    )
    if "project_ids" in params:
        stmt = stmt.bindparams(bindparam("project_ids", expanding=True))
    result = await db.execute(stmt, params)
    return [
        {
            **dict(row),
            "id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "message_id": str(row["message_id"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
        }
        for row in result.mappings()
    ]


@router.patch("/bad-cases/{bad_case_id}/resolve", response_model=dict)
async def resolve_bad_case(
    bad_case_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """标记 BadCase 为已解决。"""
    row = await db.execute(
        text("SELECT project_id FROM bad_cases WHERE id = :id"),
        {"id": str(bad_case_id)},
    )
    bad_case = row.mappings().first()
    if bad_case is None:
        raise HTTPException(status_code=404, detail="BadCase not found")
    check_project_permission(current_user, str(bad_case["project_id"]))
    await db.execute(
        text(
            """
            UPDATE bad_cases
            SET status = 'resolved', resolved_at = NOW(), updated_at = NOW()
            WHERE id = :id
            """
        ),
        {"id": str(bad_case_id)},
    )
    await db.commit()
    return {"id": str(bad_case_id), "status": "resolved"}


# --- Evaluation endpoints ---


@router.post("/runs", response_model=dict)
async def trigger_evaluation(
    data: EvaluationRunRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """触发一次 RAG 评估运行（异步）。"""
    check_project_permission(current_user, str(data.project_id))
    run_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO evaluation_runs (id, project_id, dataset_name, status, created_by)
            VALUES (:id, :project_id, :dataset_name, 'running', :created_by)
            """
        ),
        {
            "id": run_id,
            "project_id": str(data.project_id),
            "dataset_name": data.dataset_name,
            "created_by": current_user["user_id"],
        },
    )
    await db.commit()
    logger.info("Evaluation run triggered: %s for project %s", run_id, data.project_id)
    return {
        "run_id": run_id,
        "project_id": str(data.project_id),
        "status": "running",
    }


@router.get("/metrics", response_model=list[dict])
async def get_evaluation_metrics(
    project_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """获取项目的评估指标。"""
    check_project_permission(current_user, str(project_id))
    return [
        {"metric_name": "faithfulness", "metric_value": 0.0, "target": 0.90, "sample_count": 0},
        {"metric_name": "answer_relevancy", "metric_value": 0.0, "target": 0.85, "sample_count": 0},
        {"metric_name": "context_precision", "metric_value": 0.0, "target": 0.80, "sample_count": 0},
        {"metric_name": "context_recall", "metric_value": 0.0, "target": 0.85, "sample_count": 0},
    ]

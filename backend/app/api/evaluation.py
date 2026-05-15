"""RAG 评估和 BadCase 管理 API。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user

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
    current_user: Any = Depends(get_current_user),
) -> Any:
    """记录一个 BadCase（用户踩回答触发）。"""
    bad_case_id = str(uuid.uuid4())
    logger.info("BadCase created: %s by user %s", bad_case_id, current_user.id)
    return {
        "id": bad_case_id,
        "message_id": str(data.message_id),
        "category": data.category,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/bad-cases", response_model=list[dict])
async def list_bad_cases(
    project_id: uuid.UUID | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
) -> Any:
    """列出 BadCase 记录。"""
    return []


@router.patch("/bad-cases/{bad_case_id}/resolve", response_model=dict)
async def resolve_bad_case(
    bad_case_id: uuid.UUID,
    current_user: Any = Depends(get_current_user),
) -> Any:
    """标记 BadCase 为已解决。"""
    return {"id": str(bad_case_id), "status": "resolved"}


# --- Evaluation endpoints ---


@router.post("/runs", response_model=dict)
async def trigger_evaluation(
    data: EvaluationRunRequest,
    current_user: Any = Depends(get_current_user),
) -> Any:
    """触发一次 RAG 评估运行（异步）。"""
    run_id = str(uuid.uuid4())
    logger.info("Evaluation run triggered: %s for project %s", run_id, data.project_id)
    return {
        "run_id": run_id,
        "project_id": str(data.project_id),
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
    }


@router.get("/metrics", response_model=list[dict])
async def get_evaluation_metrics(
    project_id: uuid.UUID,
    current_user: Any = Depends(get_current_user),
) -> Any:
    """获取项目的评估指标。"""
    return [
        {"metric_name": "faithfulness", "metric_value": 0.0, "target": 0.90, "sample_count": 0},
        {"metric_name": "answer_relevancy", "metric_value": 0.0, "target": 0.85, "sample_count": 0},
        {"metric_name": "context_precision", "metric_value": 0.0, "target": 0.80, "sample_count": 0},
        {"metric_name": "context_recall", "metric_value": 0.0, "target": 0.85, "sample_count": 0},
    ]

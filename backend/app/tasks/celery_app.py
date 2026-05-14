"""Celery 应用配置。"""

from __future__ import annotations

import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)


def _build_redis_url(db: int) -> str:
    """Build a Redis URL from application settings.

    Falls back to ``redis://localhost:6379/<db>`` when settings cannot be
    loaded (e.g. during unit tests or before .env is available).
    """
    try:
        from app.config import get_settings

        settings = get_settings()
        password_part = f":{settings.redis.password}@" if settings.redis.password else ""
        return f"redis://{password_part}{settings.redis.host}:{settings.redis.port}/{db}"
    except Exception:
        return f"redis://localhost:6379/{db}"


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or _build_redis_url(0)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or _build_redis_url(1)

# 创建 Celery 应用
celery_app = Celery(
    "rag_agent",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery 配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务结果
    result_expires=3600,  # 结果保留 1 小时

    # 并发
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "4")),
    worker_prefetch_multiplier=1,

    # 任务路由
    task_routes={
        "backend.app.tasks.sync_tasks.sync_document_task": {"queue": "sync_queue"},
        "backend.app.tasks.sync_tasks.batch_sync_task": {"queue": "sync_queue"},
        "backend.app.tasks.sync_tasks.scheduled_sync_task": {"queue": "sync_queue"},
    },

    # 重试策略
    task_default_retry_delay=60,  # 重试间隔 60 秒
    task_max_retries=3,

    # 任务超时
    task_soft_time_limit=300,  # 软超时 5 分钟
    task_time_limit=600,       # 硬超时 10 分钟

    # Beat 定时任务
    beat_schedule={
        "scheduled-sync": {
            "task": "backend.app.tasks.sync_tasks.scheduled_sync_task",
            "schedule": int(os.getenv("SYNC_INTERVAL_SECONDS", "3600")),  # 默认每小时
            "args": (),
        },
    },
)

# 自动发现任务模块
celery_app.autodiscover_tasks(["backend.app.tasks"])

logger.info("Celery 应用已配置: broker=%s", CELERY_BROKER_URL)

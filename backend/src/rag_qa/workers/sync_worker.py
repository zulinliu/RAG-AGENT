from __future__ import annotations

import asyncio
import logging

from rag_qa.db.session import async_session_factory
from rag_qa.services.sync_service import SyncService
from rag_qa.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_datasource_task(self, datasource_id: str, task_type: str = "incremental") -> dict:
    try:
        result = asyncio.run(_execute_sync(datasource_id, task_type))
        return result
    except Exception as exc:
        logger.error("Sync task failed for datasource %s: %s", datasource_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            asyncio.run(_mark_sync_failed(datasource_id, str(exc)))
            raise


async def _execute_sync(datasource_id: str, task_type: str) -> dict:
    async with async_session_factory() as session:
        service = SyncService(session)
        sync_task = await service.execute_sync(datasource_id, task_type)
        return {
            "task_id": sync_task.id,
            "datasource_id": sync_task.datasource_id,
            "status": sync_task.status.value,
            "documents_processed": sync_task.documents_processed,
            "documents_failed": sync_task.documents_failed,
            "error_message": sync_task.error_message,
        }


async def _mark_sync_failed(datasource_id: str, error_message: str) -> None:
    async with async_session_factory() as session:
        from sqlalchemy import select

        from rag_qa.models.sync import SyncTask, SyncTaskStatus

        stmt = (
            select(SyncTask)
            .where(SyncTask.datasource_id == datasource_id)
            .order_by(SyncTask.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        if task is not None and task.status == SyncTaskStatus.RUNNING:
            task.status = SyncTaskStatus.FAILED
            task.error_message = error_message
            await session.commit()

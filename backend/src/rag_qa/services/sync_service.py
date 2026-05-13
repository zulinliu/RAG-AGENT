from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.connectors.registry import registry
from rag_qa.core.config import settings
from rag_qa.core.exceptions import ConnectorException, NotFoundException
from rag_qa.models.datasource import DataSource, DataSourceStatus
from rag_qa.models.sync import SyncTask, SyncTaskStatus, SyncTaskType

logger = logging.getLogger(__name__)

try:
    import redis
    redis_client = redis.from_url(settings.redis.url)
except Exception:
    redis_client = None


class SyncService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def trigger_sync(self, datasource_id: str, task_type: str = "incremental") -> SyncTask:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")

        sync_task_type = SyncTaskType.INCREMENTAL if task_type == "incremental" else SyncTaskType.FULL
        sync_task = SyncTask(
            datasource_id=datasource_id,
            task_type=sync_task_type,
            status=SyncTaskStatus.PENDING,
        )
        self.db.add(sync_task)

        datasource.status = DataSourceStatus.SYNCING
        await self.db.commit()
        await self.db.refresh(sync_task)

        if redis_client is not None:
            try:
                redis_client.xadd(
                    "sync_tasks",
                    {
                        "task_id": sync_task.id,
                        "datasource_id": datasource_id,
                        "task_type": task_type,
                    },
                )
            except Exception as e:
                logger.error("Failed to push sync task to Redis Streams: %s", e)

        return sync_task

    async def execute_sync(self, datasource_id: str, task_type: str = "incremental") -> SyncTask:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")

        sync_task_type = SyncTaskType.INCREMENTAL if task_type == "incremental" else SyncTaskType.FULL
        sync_task = SyncTask(
            datasource_id=datasource_id,
            task_type=sync_task_type,
            status=SyncTaskStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.db.add(sync_task)

        datasource.status = DataSourceStatus.SYNCING
        await self.db.commit()
        await self.db.refresh(sync_task)

        connector = None
        try:
            source_type = datasource.type.value
            connector = registry.get_connector(source_type, datasource.config)
            await connector.connect()

            since = datasource.last_synced_at if task_type == "incremental" else None
            changes = await connector.list_changes(since)

            documents_processed = 0
            documents_failed = 0

            for file_meta in changes:
                try:
                    local_path = await connector.download(file_meta, "/tmp/rag_qa/downloads")
                    if redis_client is not None:
                        try:
                            redis_client.xadd(
                                "doc_processing",
                                {
                                    "datasource_id": datasource_id,
                                    "project_id": datasource.project_id,
                                    "file_path": local_path,
                                    "file_name": file_meta.file_name,
                                    "file_size": str(file_meta.file_size),
                                    "mime_type": file_meta.mime_type,
                                    "checksum": file_meta.checksum or "",
                                },
                            )
                        except Exception as e:
                            logger.error("Failed to push document to processing pipeline: %s", e)
                    documents_processed += 1
                except Exception as e:
                    logger.error("Failed to download file %s: %s", file_meta.file_path, e)
                    documents_failed += 1

            sync_task.status = SyncTaskStatus.COMPLETED
            sync_task.completed_at = datetime.now(UTC)
            sync_task.documents_processed = documents_processed
            sync_task.documents_failed = documents_failed

            datasource.last_synced_at = datetime.now(UTC)
            datasource.status = DataSourceStatus.ACTIVE

        except Exception as e:
            logger.error("Sync failed for datasource %s: %s", datasource_id, e)
            sync_task.status = SyncTaskStatus.FAILED
            sync_task.completed_at = datetime.now(UTC)
            sync_task.error_message = str(e)
            datasource.status = DataSourceStatus.ERROR
        finally:
            if connector is not None:
                try:
                    await connector.disconnect()
                except Exception as e:
                    logger.error("Failed to disconnect connector: %s", e)

        await self.db.commit()
        await self.db.refresh(sync_task)
        return sync_task

    async def get_sync_status(self, datasource_id: str) -> dict:
        stmt = (
            select(SyncTask)
            .where(SyncTask.datasource_id == datasource_id)
            .order_by(SyncTask.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        latest_task = result.scalar_one_or_none()

        if latest_task is None:
            return {"datasource_id": datasource_id, "status": None, "last_sync": None}

        return {
            "datasource_id": datasource_id,
            "status": latest_task.status.value,
            "task_id": latest_task.id,
            "task_type": latest_task.task_type.value,
            "started_at": latest_task.started_at.isoformat() if latest_task.started_at else None,
            "completed_at": latest_task.completed_at.isoformat() if latest_task.completed_at else None,
            "documents_processed": latest_task.documents_processed,
            "documents_failed": latest_task.documents_failed,
            "error_message": latest_task.error_message,
            "last_sync": latest_task.completed_at.isoformat() if latest_task.completed_at else None,
        }

    async def get_sync_history(self, datasource_id: str, limit: int = 20) -> list[SyncTask]:
        stmt = (
            select(SyncTask)
            .where(SyncTask.datasource_id == datasource_id)
            .order_by(SyncTask.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

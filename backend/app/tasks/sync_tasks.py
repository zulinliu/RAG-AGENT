"""Celery 同步任务。"""

import logging
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.sync_tasks.sync_document_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_document_task(
    self: Any,
    sync_task_data: Dict[str, Any],
) -> Dict[str, Any]:
    """同步单个文档任务。

    接收 SyncTask 数据，调用 DocumentPipeline 处理文档。

    Args:
        sync_task_data: SyncTask 的字典表示

    Returns:
        处理结果字典
    """
    from app.connectors.base import SyncTask
    from app.processors.pipeline import DocumentPipeline
    from app.config import get_settings

    logger.info("开始同步文档: %s (project=%s)", sync_task_data["file_path"], sync_task_data["project_id"])

    try:
        task = SyncTask(
            source=sync_task_data["source"],
            file_path=sync_task_data["file_path"],
            project_id=sync_task_data["project_id"],
            data_source_id=sync_task_data["data_source_id"],
            file_size=sync_task_data["file_size"],
            mime_type=sync_task_data["mime_type"],
            modified_at=sync_task_data["modified_at"],
            checksum=sync_task_data.get("checksum"),
            extra=sync_task_data.get("extra", {}),
        )

        pipeline = DocumentPipeline.from_settings(get_settings())
        result = pipeline.process_document(
            file_path=task.file_path,
            project_id=task.project_id,
            data_source_id=task.data_source_id,
            mime_type=task.mime_type,
        )

        logger.info(
            "文档同步完成: %s -> %s (%d chunks)",
            task.file_path, result.status, result.chunk_count,
        )
        return {
            "document_id": result.document_id,
            "status": result.status,
            "chunk_count": result.chunk_count,
            "error_message": result.error_message,
            "duration_ms": result.duration_ms,
        }

    except Exception as e:
        logger.error("文档同步失败: %s - %s", sync_task_data.get("file_path"), e)
        # 重试
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("文档同步重试次数耗尽: %s", sync_task_data.get("file_path"))
            return {
                "document_id": sync_task_data.get("file_path", ""),
                "status": "error",
                "chunk_count": 0,
                "error_message": str(e),
            }

    # 确保始终有返回值（逻辑上不会到达这里，但满足类型检查）
    return {
        "document_id": "",
        "status": "error",
        "chunk_count": 0,
        "error_message": "unexpected",
    }


@celery_app.task(
    name="app.tasks.sync_tasks.batch_sync_task",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def batch_sync_task(
    self: Any,
    sync_tasks: List[Dict[str, Any]],
    project_id: str,
) -> Dict[str, Any]:
    """批量同步任务 — 并行 dispatch，统一等待。"""
    logger.info("开始批量同步: %d 个文件 (project=%s)", len(sync_tasks), project_id)

    results = {
        "total": len(sync_tasks),
        "success": 0,
        "skipped": 0,
        "error": 0,
        "details": [],
    }

    # 批量 dispatch 所有任务
    async_results = []
    for task_data in sync_tasks:
        r = sync_document_task.apply_async(args=[task_data], queue="sync_queue")
        async_results.append((task_data, r))

    # 并行等待所有结果
    for task_data, async_result in async_results:
        try:
            task_result = async_result.get(timeout=300)
            status = task_result.get("status", "error")

            if status == "success":
                results["success"] += 1
            elif status == "skipped":
                results["skipped"] += 1
            else:
                results["error"] += 1

            results["details"].append(task_result)

        except Exception as e:
            logger.error("批量同步中单个任务失败: %s", e)
            results["error"] += 1
            results["details"].append({
                "file_path": task_data.get("file_path", ""),
                "status": "error",
                "error_message": str(e),
            })

    logger.info(
        "批量同步完成: total=%d, success=%d, skipped=%d, error=%d",
        results["total"], results["success"], results["skipped"], results["error"],
    )
    return results


@celery_app.task(
    name="app.tasks.sync_tasks.scheduled_sync_task",
    bind=True,
)
def scheduled_sync_task(self: Any) -> Dict[str, Any]:
    """定时同步任务（由 Celery Beat 触发）。

    扫描所有已配置的数据源，检测变更并触发同步。

    Returns:
        同步结果统计
    """
    logger.info("开始定时同步任务")

    results = {
        "data_sources_scanned": 0,
        "files_detected": 0,
        "sync_triggered": 0,
        "errors": [],
    }

    try:
        # TODO: 从数据库或配置中读取所有数据源配置
        # 这里是框架代码，实际实现需要根据业务逻辑获取数据源列表
        data_sources = _get_configured_data_sources()

        for ds_config in data_sources:
            try:
                connector = _create_connector(ds_config)
                connector.connect()
                files = connector.list_files()

                results["data_sources_scanned"] += 1
                results["files_detected"] += len(files)

                # 构建同步任务
                sync_tasks = []
                for file_meta in files:
                    task_data = {
                        "source": ds_config["type"],
                        "file_path": file_meta.file_path,
                        "project_id": ds_config["project_id"],
                        "data_source_id": ds_config["id"],
                        "file_size": file_meta.file_size,
                        "mime_type": file_meta.mime_type,
                        "modified_at": file_meta.modified_at.isoformat(),
                        "extra": file_meta.extra,
                    }
                    sync_tasks.append(task_data)

                if sync_tasks:
                    batch_sync_task.delay(sync_tasks, ds_config["project_id"])
                    results["sync_triggered"] += len(sync_tasks)

                connector.disconnect()

            except Exception as e:
                logger.error("数据源同步失败: %s - %s", ds_config.get("id"), e)
                results["errors"].append({
                    "data_source_id": ds_config.get("id", ""),
                    "error": str(e),
                })

    except Exception as e:
        logger.error("定时同步任务异常: %s", e)
        results["errors"].append({"error": str(e)})

    logger.info("定时同步完成: %s", results)
    return results


# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------

def _get_configured_data_sources() -> List[Dict[str, Any]]:
    """从数据库获取所有活跃的、状态为 idle 的数据源配置。"""
    from app.config import get_settings

    settings = get_settings()
    sync_url = settings.db.sync_url

    try:
        from sqlalchemy import create_engine, select, text
        from sqlalchemy.orm import Session

        engine = create_engine(sync_url, pool_size=2, max_overflow=3)

        with Session(engine) as session:
            rows = session.execute(
                text(
                    """
                    SELECT id, project_id, source_type, config, name
                    FROM data_sources
                    WHERE is_active = true AND sync_status = 'idle'
                    """
                )
            ).fetchall()

            result: List[Dict[str, Any]] = []
            for row in rows:
                result.append({
                    "id": str(row.id),
                    "project_id": str(row.project_id),
                    "type": row.source_type,
                    "config": row.config or {},
                    "name": row.name,
                    # Flatten config fields that _create_connector expects at top level
                    "path": (row.config or {}).get("path", ""),
                    "server_url": (row.config or {}).get("server_url", ""),
                    "token": (row.config or {}).get("access_token", ""),
                    "repo_id": (row.config or {}).get("repo_id", ""),
                    "sync_dir": (row.config or {}).get("sync_dir", "/"),
                    "allowed_extensions": (row.config or {}).get("allowed_extensions"),
                    "protocol": (row.config or {}).get("protocol", "nfs"),
                    "host": (row.config or {}).get("host"),
                    "share_name": (row.config or {}).get("share_name"),
                    "username": (row.config or {}).get("username"),
                    "password": (row.config or {}).get("password"),
                    "mount_point": (row.config or {}).get("mount_point"),
                    "remote_path": (row.config or {}).get("remote_path", "/"),
                    "mode": (row.config or {}).get("mode", "api"),
                    "app_key": (row.config or {}).get("app_key"),
                    "app_secret": (row.config or {}).get("app_secret"),
                    "cli_path": (row.config or {}).get("cli_path"),
                })

            engine.dispose()
            return result

    except Exception as e:
        logger.error("读取数据源配置失败: %s", e)
        return []


def _create_connector(config: Dict[str, Any]) -> Any:
    """根据配置创建连接器实例。"""
    from app.connectors.local import LocalConnector
    from app.connectors.seafile import SeafileConnector
    from app.connectors.nas import NASConnector
    from app.connectors.dingtalk import DingTalkConnector

    ds_type = config.get("type", "").lower()
    if ds_type == "local":
        return LocalConnector(
            watch_dir=config["path"],
            allowed_extensions=config.get("allowed_extensions"),
            project_id=config.get("project_id", ""),
            datasource_id=config.get("id", ""),
        )
    elif ds_type == "seafile":
        return SeafileConnector(
            server_url=config["server_url"],
            token=config["token"],
            repo_id=config["repo_id"],
            sync_dir=config.get("sync_dir", "/"),
            allowed_extensions=config.get("allowed_extensions"),
        )
    elif ds_type == "nas":
        return NASConnector(
            protocol=config.get("protocol", "nfs"),
            host=config.get("host"),
            share_name=config.get("share_name"),
            username=config.get("username"),
            password=config.get("password"),
            mount_point=config.get("mount_point"),
            remote_path=config.get("remote_path", "/"),
            allowed_extensions=config.get("allowed_extensions"),
        )
    elif ds_type == "dingtalk":
        return DingTalkConnector(
            mode=config.get("mode", "api"),
            app_key=config.get("app_key"),
            app_secret=config.get("app_secret"),
            cli_path=config.get("cli_path"),
        )
    else:
        raise ValueError(f"不支持的数据源类型: {ds_type}")

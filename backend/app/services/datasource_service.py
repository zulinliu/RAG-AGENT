"""Data source management service.

Handles data source CRUD, connection testing, and sync triggering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import DataSource, Project
from app.schemas.datasource import ConnectionTestResult, SyncStatus


class DataSourceService:
    """Business logic for data source management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_data_source(
        self,
        project_id: uuid.UUID,
        source_type: str,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> DataSource:
        """Create a new data source within a project.

        Args:
            project_id: Owning project.
            source_type: One of ``local``, ``seafile``, ``nas``, ``dingtalk``.
            name: Display name.
            config: Connector-specific configuration dict.

        Returns:
            The newly created ``DataSource``.

        Raises:
            ValueError: If the project is not found.
        """
        project = await self._db.get(Project, project_id)
        if project is None or not project.is_active:
            raise ValueError(f"Project not found: {project_id}")

        data_source = DataSource(
            project_id=project_id,
            source_type=source_type,
            name=name,
            config=config or {},
        )
        self._db.add(data_source)
        await self._db.flush()
        return data_source

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_data_source(self, data_source_id: uuid.UUID) -> DataSource:
        """Retrieve a data source by ID.

        Raises:
            ValueError: If the data source is not found.
        """
        ds = await self._db.get(DataSource, data_source_id)
        if ds is None:
            raise ValueError(f"Data source not found: {data_source_id}")
        return ds

    async def list_data_sources(
        self,
        project_id: uuid.UUID,
    ) -> Sequence[DataSource]:
        """List all active data sources for a project."""
        result = await self._db.execute(
            select(DataSource)
            .where(
                DataSource.project_id == project_id,
                DataSource.is_active == True,  # noqa: E712
            )
            .order_by(DataSource.name),
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_data_source(
        self,
        data_source_id: uuid.UUID,
        **kwargs: Any,
    ) -> DataSource:
        """Update mutable data source fields.

        Acceptable keyword arguments: name, config, is_active.

        Raises:
            ValueError: If the data source is not found.
        """
        ds = await self.get_data_source(data_source_id)

        allowed_fields = {"name", "config", "is_active"}
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(ds, field, value)

        await self._db.flush()
        return ds

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_data_source(self, data_source_id: uuid.UUID) -> None:
        """Soft-delete a data source.

        Raises:
            ValueError: If the data source is not found.
        """
        ds = await self.get_data_source(data_source_id)
        ds.is_active = False
        await self._db.flush()

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(
        self,
        data_source_id: uuid.UUID,
    ) -> ConnectionTestResult:
        """Test connectivity to the external data source.

        This is a placeholder that performs basic validation. Real
        connector-specific logic will be added when connectors are
        implemented in Phase 3.

        Returns:
            ``ConnectionTestResult`` with success status.
        """
        ds = await self.get_data_source(data_source_id)

        try:
            source_type = ds.source_type
            config = ds.config or {}

            # Basic validation per source type
            if source_type == "local":
                path = config.get("path", "")
                if not path:
                    return ConnectionTestResult(
                        success=False,
                        message="Local path not configured",
                    )

            elif source_type == "seafile":
                url = config.get("server_url", "")
                token = config.get("access_token", "")
                if not url or not token:
                    return ConnectionTestResult(
                        success=False,
                        message="Seafile server URL or access token not configured",
                    )

            elif source_type == "nas":
                host = config.get("host", "")
                protocol = config.get("protocol", "")
                if not host:
                    return ConnectionTestResult(
                        success=False,
                        message="NAS host not configured",
                    )

            elif source_type == "dingtalk":
                app_key = config.get("app_key", "")
                app_secret = config.get("app_secret", "")
                if not app_key or not app_secret:
                    return ConnectionTestResult(
                        success=False,
                        message="DingTalk app_key or app_secret not configured",
                    )

            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Unknown source type: {source_type}",
                )

            return ConnectionTestResult(
                success=True,
                message=f"Connection to {source_type} data source validated",
            )

        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def trigger_sync(self, data_source_id: uuid.UUID) -> None:
        """Trigger an asynchronous sync task via Celery.

        Updates the data source status to ``syncing`` and dispatches a
        Celery task for the actual sync work.

        Raises:
            ValueError: If the data source is not found.
        """
        ds = await self.get_data_source(data_source_id)
        ds.sync_status = "syncing"
        await self._db.flush()

        # Dispatch Celery task (imported lazily to avoid circular imports)
        try:
            from app.tasks.sync_tasks import batch_sync_task

            batch_sync_task.delay([], str(ds.project_id))
        except ImportError:
            # Tasks module not yet implemented; status will remain syncing
            pass

    async def get_sync_status(
        self,
        data_source_id: uuid.UUID,
    ) -> SyncStatus:
        """Return the current sync status for a data source.

        Raises:
            ValueError: If the data source is not found.
        """
        ds = await self.get_data_source(data_source_id)

        # Count related documents by status
        from sqlalchemy import func as sa_func

        from app.models.document import Document

        result = await self._db.execute(
            select(Document.status, sa_func.count())
            .where(Document.data_source_id == data_source_id)
            .group_by(Document.status),
        )
        status_counts = dict(result.all())

        return SyncStatus(
            data_source_id=ds.id,
            status=ds.sync_status,
            last_synced_at=ds.last_synced_at,
            total_documents=sum(status_counts.values()),
            pending_documents=status_counts.get("pending", 0),
            failed_documents=status_counts.get("failed", 0),
        )

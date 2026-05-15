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
            config=_normalize_config(config or {}),
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
                if field == "config" and value is not None:
                    value = _normalize_config(value)
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

    @staticmethod
    async def test_connection_with_config(
        source_type: str,
        config: dict[str, Any],
    ) -> ConnectionTestResult:
        """Test connectivity using raw config (no DB session needed).

        Validates the config for the given source_type without requiring
        a persisted data source record.

        Args:
            source_type: One of local, seafile, nas, dingtalk.
            config: Connector-specific configuration dict.

        Returns:
            ConnectionTestResult with success status.
        """
        config = _normalize_config(config)
        try:
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
                if not host:
                    return ConnectionTestResult(
                        success=False,
                        message="NAS host not configured",
                    )

            elif source_type == "dingtalk":
                mode = config.get("mode", "api")
                app_key = config.get("app_key", "")
                app_secret = config.get("app_secret", "")
                if mode == "api" and (not app_key or not app_secret):
                    return ConnectionTestResult(
                        success=False,
                        message="DingTalk app_key or app_secret not configured",
                    )

            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Unknown source type: {source_type}",
                )

            import asyncio

            connector = _instantiate_connector(source_type, config)
            try:
                await asyncio.to_thread(connector.connect)
            finally:
                try:
                    connector.disconnect()
                except Exception:
                    pass

            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to {source_type} data source",
            )

        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {exc}",
            )

    async def test_connection(
        self,
        data_source_id: uuid.UUID,
    ) -> ConnectionTestResult:
        """Test connectivity to the external data source.

        Instantiates the corresponding connector and attempts to connect.
        Returns success/failure with an error message.

        Returns:
            ``ConnectionTestResult`` with success status.
        """
        ds = await self.get_data_source(data_source_id)

        try:
            source_type = ds.source_type
            config = _normalize_config(ds.config or {})

            # Basic config validation before attempting real connection
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
                if not host:
                    return ConnectionTestResult(
                        success=False,
                        message="NAS host not configured",
                    )

            elif source_type == "dingtalk":
                mode = config.get("mode", "api")
                app_key = config.get("app_key", "")
                app_secret = config.get("app_secret", "")
                if mode == "api" and (not app_key or not app_secret):
                    return ConnectionTestResult(
                        success=False,
                        message="DingTalk app_key or app_secret not configured",
                    )

            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"Unknown source type: {source_type}",
                )

            # --- Real connection test via connector ---
            import asyncio

            connector = _instantiate_connector(source_type, config)

            try:
                # connect() is synchronous — run in thread to avoid blocking the event loop
                await asyncio.to_thread(connector.connect)
            except Exception as conn_exc:
                return ConnectionTestResult(
                    success=False,
                    message=f"Connection failed: {conn_exc}",
                )
            finally:
                try:
                    connector.disconnect()
                except Exception:
                    pass

            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to {source_type} data source",
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
            from app.tasks.sync_tasks import sync_data_source_task

            sync_data_source_task.delay(str(ds.id))
        except ImportError:
            # Worker package unavailable in minimal API-only environments.
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


def _normalize_allowed_extensions(raw: Any) -> list[str] | None:
    """Normalize pattern/extension config into ['.pdf', '.md'] format."""
    if raw in (None, "", "*", "*.*"):
        return None
    values: list[Any]
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, list):
        values = raw
    else:
        return None

    result: list[str] = []
    for item in values:
        value = str(item).strip().lower()
        if not value or value in ("*", "*.*"):
            continue
        if value.startswith("*."):
            value = value[1:]
        elif not value.startswith("."):
            value = f".{value}"
        result.append(value)
    return sorted(set(result)) or None


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize connector config while preserving original input fields."""
    normalized = dict(config or {})
    extensions = _normalize_allowed_extensions(
        normalized.get("allowed_extensions")
        or normalized.get("pattern")
        or normalized.get("patterns")
    )
    if extensions is not None:
        normalized["allowed_extensions"] = extensions
    return normalized


def _extension_set(config: dict[str, Any]) -> set[str] | None:
    extensions = config.get("allowed_extensions")
    return set(extensions) if extensions else None


def _instantiate_connector(source_type: str, config: dict[str, Any]) -> Any:
    """Create a connector instance from source type and config dict."""
    from app.connectors.local import LocalConnector
    from app.connectors.seafile import SeafileConnector
    from app.connectors.nas import NASConnector
    from app.connectors.dingtalk import DingTalkConnector

    config = _normalize_config(config)

    if source_type == "local":
        return LocalConnector(
            watch_dir=config["path"],
            allowed_extensions=_extension_set(config),
        )

    elif source_type == "seafile":
        return SeafileConnector(
            server_url=config["server_url"],
            token=config.get("access_token", ""),
            repo_id=config.get("repo_id", ""),
            allowed_extensions=_extension_set(config),
        )

    elif source_type == "nas":
        return NASConnector(
            protocol=config.get("protocol", "nfs"),
            host=config.get("host"),
            share_name=config.get("share_name"),
            username=config.get("username"),
            password=config.get("password"),
            mount_point=config.get("mount_point"),
            remote_path=config.get("remote_path", "/"),
            allowed_extensions=_extension_set(config),
        )

    elif source_type == "dingtalk":
        return DingTalkConnector(
            mode=config.get("mode", "api"),
            app_key=config.get("app_key"),
            app_secret=config.get("app_secret"),
            cli_path=config.get("cli_path"),
        )

    else:
        raise ValueError(f"Unknown source type: {source_type}")

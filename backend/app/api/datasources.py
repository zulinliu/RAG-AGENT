"""Data source API routes.

Provides CRUD, connection testing, and sync management for data sources.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import DetailResponse
from app.schemas.datasource import (
    ConnectionTestResult,
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    SyncStatus,
)
from app.services.datasource_service import DataSourceService
from app.utils.auth import (
    PermissionChecker,
    check_project_permission,
    get_current_user,
)

router = APIRouter(tags=["Data Sources"])


# ---------------------------------------------------------------------------
# Request schema for connection test with raw config
# ---------------------------------------------------------------------------


class ConnectionTestRequest(BaseModel):
    """Request body for testing a connection with raw config (no persisted datasource)."""

    source_type: str = Field(..., description="One of: local, seafile, nas, dingtalk")
    config: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# POST /api/v1/datasources/test-connection
# ---------------------------------------------------------------------------


@router.post(
    "/datasources/test-connection",
    response_model=ConnectionTestResult,
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def test_connection_with_config(
    body: ConnectionTestRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ConnectionTestResult:
    """Test connectivity using provided config without persisting a data source."""
    return await DataSourceService.test_connection_with_config(
        source_type=body.source_type,
        config=body.config,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/datasources
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/datasources",
    response_model=DataSourceResponse,
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def create_data_source(
    project_id: str,
    body: DataSourceCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """Create a new data source within a project."""
    check_project_permission(current_user, project_id)

    svc = DataSourceService(db)
    try:
        ds = await svc.create_data_source(
            project_id=uuid.UUID(project_id),
            source_type=body.source_type,
            name=body.name,
            config=body.config,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _datasource_to_response(ds)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/datasources
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/datasources",
    response_model=list[DataSourceResponse],
)
async def list_data_sources(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DataSourceResponse]:
    """List all data sources for a project."""
    check_project_permission(current_user, project_id)

    svc = DataSourceService(db)
    sources = await svc.list_data_sources(uuid.UUID(project_id))
    return [_datasource_to_response(ds) for ds in sources]


# ---------------------------------------------------------------------------
# PUT /api/v1/datasources/{data_source_id}
# ---------------------------------------------------------------------------


@router.put(
    "/datasources/{data_source_id}",
    response_model=DataSourceResponse,
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def update_data_source(
    data_source_id: str,
    body: DataSourceUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """Update a data source."""
    svc = DataSourceService(db)
    try:
        ds = await svc.update_data_source(
            uuid.UUID(data_source_id),
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(ds.project_id))
    return _datasource_to_response(ds)


# ---------------------------------------------------------------------------
# DELETE /api/v1/datasources/{data_source_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/datasources/{data_source_id}",
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin"})),
    ],
)
async def delete_data_source(
    data_source_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DetailResponse:
    """Soft-delete a data source."""
    svc = DataSourceService(db)
    try:
        ds = await svc.get_data_source(uuid.UUID(data_source_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(ds.project_id))
    await svc.delete_data_source(ds.id)
    return DetailResponse(detail="Data source deleted")


# ---------------------------------------------------------------------------
# POST /api/v1/datasources/{data_source_id}/test
# ---------------------------------------------------------------------------


@router.post(
    "/datasources/{data_source_id}/test",
    response_model=ConnectionTestResult,
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def test_connection(
    data_source_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionTestResult:
    """Test connectivity to a data source."""
    svc = DataSourceService(db)
    try:
        ds = await svc.get_data_source(uuid.UUID(data_source_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(ds.project_id))
    return await svc.test_connection(ds.id)


# ---------------------------------------------------------------------------
# POST /api/v1/datasources/{data_source_id}/sync
# ---------------------------------------------------------------------------


@router.post(
    "/datasources/{data_source_id}/sync",
    dependencies=[
        Depends(PermissionChecker(roles={"system_admin", "project_admin", "knowledge_admin"})),
    ],
)
async def trigger_sync(
    data_source_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DetailResponse:
    """Trigger a manual sync for a data source."""
    svc = DataSourceService(db)
    try:
        ds = await svc.get_data_source(uuid.UUID(data_source_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(ds.project_id))
    await svc.trigger_sync(ds.id)
    return DetailResponse(detail="Sync triggered")


# ---------------------------------------------------------------------------
# GET /api/v1/datasources/{data_source_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/datasources/{data_source_id}/status",
    response_model=SyncStatus,
)
async def get_sync_status(
    data_source_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncStatus:
    """Get the current sync status of a data source."""
    svc = DataSourceService(db)
    try:
        ds = await svc.get_data_source(uuid.UUID(data_source_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    check_project_permission(current_user, str(ds.project_id))
    return await svc.get_sync_status(ds.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SENSITIVE_SUBSTRINGS = ("password", "secret", "token", "key")


def _is_sensitive_key(key: str) -> bool:
    """Check if a config key looks sensitive."""
    lower = key.lower()
    return any(s in lower for s in SENSITIVE_SUBSTRINGS)


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive fields in data source config."""
    return {
        key: ("********" if value and _is_sensitive_key(key) else value)
        for key, value in config.items()
    }


def _datasource_to_response(ds: Any) -> DataSourceResponse:
    """Map an ORM DataSource to a response schema."""
    raw_config = ds.config or {}
    return DataSourceResponse(
        id=ds.id,
        project_id=ds.project_id,
        source_type=ds.source_type,
        name=ds.name,
        config=_sanitize_config(raw_config),
        sync_status=ds.sync_status,
        last_synced_at=ds.last_synced_at,
        is_active=ds.is_active,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )

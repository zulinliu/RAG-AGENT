"""Data source API routes.

Provides CRUD, connection testing, and sync management for data sources.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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

    import uuid

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

    import uuid

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
    import uuid

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
) -> dict[str, str]:
    """Soft-delete a data source."""
    import uuid

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
    return {"detail": "Data source deleted"}


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
    import uuid

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
) -> dict[str, str]:
    """Trigger a manual sync for a data source."""
    import uuid

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
    return {"detail": "Sync triggered"}


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
    import uuid

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

SENSITIVE_CONFIG_KEYS = {"password", "secret", "token", "api_key", "app_secret", "access_key", "secret_key"}


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive fields in data source config."""
    sanitized = {}
    for key, value in config.items():
        if key.lower() in SENSITIVE_CONFIG_KEYS or any(s in key.lower() for s in ("password", "secret", "token", "key")):
            sanitized[key] = "********" if value else value
        else:
            sanitized[key] = value
    return sanitized


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

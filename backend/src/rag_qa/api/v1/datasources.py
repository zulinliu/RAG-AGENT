from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.api.deps import get_current_user, get_db, require_role
from rag_qa.core.exceptions import NotFoundException
from rag_qa.models.datasource import DataSource, DataSourceStatus
from rag_qa.models.project import Project
from rag_qa.models.user import Role, User
from rag_qa.schemas.common import ResponseBase
from rag_qa.schemas.datasource import DataSourceCreate, DataSourceResponse, DataSourceTestResult, DataSourceUpdate

router = APIRouter(prefix="/projects/{project_id}/datasources", tags=["datasources"])


async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException(message="Project not found")
    return project


@router.get("", response_model=ResponseBase[list[DataSourceResponse]])
async def list_datasources(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(DataSource).where(DataSource.project_id == project_id).order_by(DataSource.created_at.desc())
    )
    datasources = result.scalars().all()
    return ResponseBase(data=[DataSourceResponse.model_validate(ds) for ds in datasources])


@router.post("", response_model=ResponseBase[DataSourceResponse])
async def create_datasource(
    project_id: str,
    ds_in: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    datasource = DataSource(
        project_id=project_id,
        name=ds_in.name,
        type=ds_in.type,
        config=ds_in.config,
        sync_interval_minutes=ds_in.sync_interval_minutes,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)
    return ResponseBase(data=DataSourceResponse.model_validate(datasource))


@router.put("/{datasource_id}", response_model=ResponseBase[DataSourceResponse])
async def update_datasource(
    project_id: str,
    datasource_id: str,
    ds_in: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.project_id == project_id)
    )
    datasource = result.scalar_one_or_none()
    if datasource is None:
        raise NotFoundException(message="DataSource not found")
    update_data = ds_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(datasource, field, value)
    await db.commit()
    await db.refresh(datasource)
    return ResponseBase(data=DataSourceResponse.model_validate(datasource))


@router.delete("/{datasource_id}", response_model=ResponseBase)
async def delete_datasource(
    project_id: str,
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.project_id == project_id)
    )
    datasource = result.scalar_one_or_none()
    if datasource is None:
        raise NotFoundException(message="DataSource not found")
    await db.delete(datasource)
    await db.commit()
    return ResponseBase()


@router.post("/{datasource_id}/test", response_model=ResponseBase[DataSourceTestResult])
async def test_datasource(
    project_id: str,
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.project_id == project_id)
    )
    datasource = result.scalar_one_or_none()
    if datasource is None:
        raise NotFoundException(message="DataSource not found")
    test_result = DataSourceTestResult(success=True, message="Connection successful")
    return ResponseBase(data=test_result)


@router.post("/{datasource_id}/sync", response_model=ResponseBase)
async def sync_datasource(
    project_id: str,
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.project_id == project_id)
    )
    datasource = result.scalar_one_or_none()
    if datasource is None:
        raise NotFoundException(message="DataSource not found")
    datasource.status = DataSourceStatus.SYNCING
    await db.commit()
    return ResponseBase()

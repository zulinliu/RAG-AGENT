from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.api.deps import get_current_user, get_db, require_role
from rag_qa.core.exceptions import ConflictException, NotFoundException
from rag_qa.models.project import Project, ProjectMember, ProjectMemberRole, ProjectStatus
from rag_qa.models.user import Role, User
from rag_qa.schemas.common import PageData, PageResponse, ResponseBase
from rag_qa.schemas.project import MemberAdd, MemberResponse, ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=PageResponse[ProjectResponse])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Project).where(Project.status == ProjectStatus.ACTIVE)
    if current_user.role != Role.SYSTEM_ADMIN:
        query = query.join(ProjectMember).where(ProjectMember.user_id == current_user.id)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PageResponse(
        data=PageData(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.post("", response_model=ResponseBase[ProjectResponse])
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    project = Project(
        name=project_in.name,
        description=project_in.description,
    )
    db.add(project)
    await db.flush()
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role=ProjectMemberRole.ADMIN,
    )
    db.add(member)
    await db.commit()
    await db.refresh(project)
    return ResponseBase(data=ProjectResponse.model_validate(project))


@router.get("/{project_id}", response_model=ResponseBase[ProjectResponse])
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException(message="Project not found")
    return ResponseBase(data=ProjectResponse.model_validate(project))


@router.put("/{project_id}", response_model=ResponseBase[ProjectResponse])
async def update_project(
    project_id: str,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException(message="Project not found")
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ResponseBase(data=ProjectResponse.model_validate(project))


@router.delete("/{project_id}", response_model=ResponseBase)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException(message="Project not found")
    await db.delete(project)
    await db.commit()
    return ResponseBase()


@router.post("/{project_id}/members", response_model=ResponseBase)
async def add_member(
    project_id: str,
    member_in: MemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if result.scalar_one_or_none() is None:
        raise NotFoundException(message="Project not found")
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_in.user_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictException(message="User is already a member of this project")
    member = ProjectMember(
        project_id=project_id,
        user_id=member_in.user_id,
        role=member_in.role,
    )
    db.add(member)
    await db.commit()
    return ResponseBase()


@router.get("/{project_id}/members", response_model=ResponseBase[list[MemberResponse]])
async def list_members(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = result.scalars().all()
    member_responses = []
    for m in members:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        user = user_result.scalar_one_or_none()
        member_responses.append(
            MemberResponse(
                id=m.id,
                user_id=m.user_id,
                username=user.username if user else "",
                display_name=user.display_name if user else None,
                role=m.role,
                joined_at=m.created_at,
            )
        )
    return ResponseBase(data=member_responses)


@router.delete("/{project_id}/members/{user_id}", response_model=ResponseBase)
async def remove_member(
    project_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundException(message="Member not found")
    await db.delete(member)
    await db.commit()
    return ResponseBase()

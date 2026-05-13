"""Project management API routes.

Provides CRUD operations for projects and project-member management.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService
from app.services.user_service import UserService
from app.utils.auth import (
    PermissionChecker,
    check_project_permission,
    get_current_user,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


# ---------------------------------------------------------------------------
# POST /api/v1/projects
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker(roles={"system_admin", "project_admin"}))],
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project."""
    svc = ProjectService(db)
    project = await svc.create_project(
        name=body.name,
        description=body.description,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description or "",
        is_deleted=not project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """List projects the current user has access to.

    System admins see all active projects.
    """
    import uuid

    svc = ProjectService(db)
    user_id = None if current_user.get("role") == "system_admin" else uuid.UUID(
        current_user["user_id"],
    )
    projects = await svc.list_projects(user_id=user_id)

    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description or "",
            is_deleted=not p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project details."""
    check_project_permission(current_user, project_id)

    svc = ProjectService(db)
    try:
        project = await svc.get_project(project_id)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description or "",
        is_deleted=not project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(PermissionChecker(roles={"system_admin", "project_admin"}))],
)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project."""
    check_project_permission(current_user, project_id)

    svc = ProjectService(db)
    try:
        project = await svc.update_project(
            project_id,  # type: ignore[arg-type]
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description or "",
        is_deleted=not project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{project_id}",
    dependencies=[Depends(PermissionChecker(roles={"system_admin"}))],
)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Soft-delete a project (system admin only)."""
    svc = ProjectService(db)
    try:
        await svc.delete_project(project_id)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {"detail": "Project deleted"}


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/members
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    dependencies=[Depends(PermissionChecker(roles={"system_admin", "project_admin"}))],
)
async def add_project_member(
    project_id: str,
    body: ProjectMemberCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberResponse:
    """Add a user to a project with a specified role."""
    check_project_permission(current_user, project_id)

    svc = UserService(db)
    try:
        assoc = await svc.assign_project_role(
            user_id=body.user_id,
            project_id=body.user_id.__class__(project_id),
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ProjectMemberResponse(
        id=assoc.id,
        user_id=assoc.user_id,
        project_id=assoc.project_id,
        role=assoc.role,
        created_at=assoc.created_at,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/members
# ---------------------------------------------------------------------------


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMemberResponse]:
    """List all members of a project."""
    check_project_permission(current_user, project_id)

    import uuid

    svc = UserService(db)
    members = await svc.get_project_members(uuid.UUID(project_id))

    result = []
    for m in members:
        result.append(
            ProjectMemberResponse(
                id=m.id,
                user_id=m.user_id,
                project_id=m.project_id,
                role=m.role,
                username=m.user.username if m.user else None,
                email=m.user.email if m.user else None,
                created_at=m.created_at,
            ),
        )
    return result


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}/members/{user_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{project_id}/members/{user_id}",
    dependencies=[Depends(PermissionChecker(roles={"system_admin", "project_admin"}))],
)
async def remove_project_member(
    project_id: str,
    user_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove a user from a project."""
    check_project_permission(current_user, project_id)

    import uuid

    svc = UserService(db)
    try:
        await svc.remove_project_role(
            user_id=uuid.UUID(user_id),
            project_id=uuid.UUID(project_id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {"detail": "Member removed"}

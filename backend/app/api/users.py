"""User management API routes.

Provides user listing, detail, update, and role management.
All endpoints require at least ``project_admin`` role.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import (
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
)
from app.services.user_service import UserService
from app.utils.auth import PermissionChecker, get_current_user

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(PermissionChecker(roles={"system_admin", "project_admin"}))],
)


# ---------------------------------------------------------------------------
# GET /api/v1/users
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[UserResponse])
async def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """List all users (admin only)."""
    svc = UserService(db)
    users, _total = await svc.list_users(offset=(page - 1) * size, limit=size)

    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
            project_ids=[str(a.project_id) for a in u.project_associations],
        )
        for u in users
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get user details by ID."""
    svc = UserService(db)
    try:
        user = await svc.get_user(uuid.UUID(user_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        project_ids=[str(a.project_id) for a in user.project_associations],
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{user_id}
# ---------------------------------------------------------------------------


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user information."""
    svc = UserService(db)

    update_data = body.model_dump(exclude_unset=True)
    # Map 'password' from schema to service
    password = update_data.pop("password", None)
    if password is not None:
        update_data["password"] = password

    try:
        user = await svc.update_user(uuid.UUID(user_id), **update_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        project_ids=[str(a.project_id) for a in user.project_associations],
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{user_id}/role
# ---------------------------------------------------------------------------


@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(PermissionChecker(roles={"system_admin"}))],
)
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user's system role (system admin only)."""
    svc = UserService(db)
    try:
        user = await svc.update_user(uuid.UUID(user_id), role=body.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        project_ids=[str(a.project_id) for a in user.project_associations],
    )

"""Authentication API routes.

Provides login, register, user profile, logout, and password change endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    PasswordChange,
    UserCreate,
    UserResponse,
)
from app.services.user_service import UserService
from app.utils.auth import PermissionChecker, get_current_user, revoke_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate a user and return a JWT token."""
    svc = UserService(db)
    try:
        token = await svc.authenticate(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user = await svc.get_user_by_username(body.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated user not found",
        )

    project_ids = [str(assoc.project_id) for assoc in user.project_associations]
    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            project_ids=project_ids,
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register  (admin only)
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    dependencies=[Depends(PermissionChecker(roles={"system_admin"}))],
)
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user. Only system admins may call this endpoint."""
    svc = UserService(db)
    try:
        user = await svc.create_user(
            username=body.username,
            email=body.email,
            password=body.password,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
        project_ids=[],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    import uuid

    svc = UserService(db)
    user = await svc.get_user(uuid.UUID(current_user["user_id"]))

    project_ids = [str(assoc.project_id) for assoc in user.project_associations]
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        project_ids=project_ids,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke the current JWT token (logout)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        await revoke_token(token, request)
    return {"detail": "Logged out successfully"}


# ---------------------------------------------------------------------------
# PUT /api/v1/auth/password
# ---------------------------------------------------------------------------


@router.put("/password")
async def change_password(
    request: Request,
    body: PasswordChange,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Change the current user's password."""
    import uuid

    from app.utils.auth import verify_password as _verify

    svc = UserService(db)
    user = await svc.get_user(uuid.UUID(current_user["user_id"]))

    if not _verify(body.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    await svc.update_user(user.id, password=body.new_password)

    # Revoke the current token so the user must re-authenticate
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        await revoke_token(token, request)

    return {"detail": "Password changed successfully"}

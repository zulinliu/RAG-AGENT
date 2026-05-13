"""Pydantic schemas for user-related API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Request body for ``POST /api/v1/auth/login``."""

    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserCreate(BaseModel):
    """Request body for creating a new user (admin only)."""

    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"system_admin", "project_admin", "knowledge_admin", "user", "readonly"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v


class UserUpdate(BaseModel):
    """Request body for updating an existing user."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"system_admin", "project_admin", "knowledge_admin", "user", "readonly"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v


class PasswordChange(BaseModel):
    """Request body for changing the current user's password."""

    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class UserRoleUpdate(BaseModel):
    """Request body for updating a user's role."""

    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"system_admin", "project_admin", "knowledge_admin", "user", "readonly"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Serialized user representation returned in API responses."""

    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    project_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response body for a successful login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Decoded JWT token payload exposed internally."""

    user_id: str
    username: str
    role: str
    project_ids: list[str] = Field(default_factory=list)
    exp: int | None = None
    iat: int | None = None
    jti: str | None = None

    model_config = {"from_attributes": True}

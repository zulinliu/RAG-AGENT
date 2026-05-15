"""Pydantic schemas for user-related API endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_password_complexity(v: str) -> str:
    """Ensure password meets complexity requirements.

    - At least 8 characters
    - Contains at least 2 of: uppercase, lowercase, digit
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    categories = 0
    if re.search(r'[A-Z]', v):
        categories += 1
    if re.search(r'[a-z]', v):
        categories += 1
    if re.search(r'\d', v):
        categories += 1
    if categories < 2:
        raise ValueError(
            "Password must contain at least 2 of: uppercase letters, "
            "lowercase letters, digits"
        )
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Request body for ``POST /api/v1/auth/login``."""

    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class UserCreate(BaseModel):
    """Request body for creating a new user (admin only)."""

    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="user")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

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
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_password_complexity(v)

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

    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


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

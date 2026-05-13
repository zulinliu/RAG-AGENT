"""Pydantic schemas for project-related API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    """Request body for ``POST /api/v1/projects``."""

    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    """Request body for ``PUT /api/v1/projects/{id}``."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)


class ProjectMemberCreate(BaseModel):
    """Request body for ``POST /api/v1/projects/{id}/members``."""

    user_id: uuid.UUID
    role: str = Field(default="user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"project_admin", "knowledge_admin", "user", "readonly"}
        if v not in allowed:
            raise ValueError(f"Project role must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProjectResponse(BaseModel):
    """Serialized project representation."""

    id: uuid.UUID
    name: str
    description: str
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    """Serialized project-member association."""

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    role: str
    username: str | None = None
    email: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

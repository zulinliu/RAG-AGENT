from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from rag_qa.models.project import ProjectMemberRole, ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_id: str
    role: ProjectMemberRole = ProjectMemberRole.MEMBER


class MemberResponse(BaseModel):
    id: str
    user_id: str
    username: str
    display_name: str | None
    role: ProjectMemberRole
    joined_at: datetime

    model_config = {"from_attributes": True}

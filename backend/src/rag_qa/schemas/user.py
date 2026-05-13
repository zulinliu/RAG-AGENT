from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from rag_qa.models.user import Role


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    role: Role = Field(default=Role.MEMBER)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str | None
    role: Role
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str | None = None
    role: Role | None = None

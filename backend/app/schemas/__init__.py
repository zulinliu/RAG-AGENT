"""Shared Pydantic response schemas used across multiple API routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetailResponse(BaseModel):
    """Simple detail message response for mutating endpoints."""

    detail: str


class UploadResponse(BaseModel):
    """Response for file upload endpoints."""

    detail: str
    document_id: str = Field(default="")

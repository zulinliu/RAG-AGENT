"""Pydantic schemas for data-source-related API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DataSourceCreate(BaseModel):
    """Request body for ``POST /api/v1/projects/{project_id}/datasources``."""

    source_type: str
    name: str = Field(..., min_length=1, max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"local", "seafile", "nas", "dingtalk"}
        if v not in allowed:
            raise ValueError(f"source_type must be one of {allowed}")
        return v


class DataSourceUpdate(BaseModel):
    """Request body for ``PUT /api/v1/datasources/{id}``."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DataSourceResponse(BaseModel):
    """Serialized data source representation."""

    id: uuid.UUID
    project_id: uuid.UUID
    source_type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    sync_status: str = "idle"
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResult(BaseModel):
    """Result of testing a data source connection."""

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SyncStatus(BaseModel):
    """Current synchronization status of a data source."""

    data_source_id: uuid.UUID
    status: str  # idle, syncing, error
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    total_documents: int = 0
    pending_documents: int = 0
    failed_documents: int = 0

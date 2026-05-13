from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from rag_qa.models.datasource import DataSourceStatus, DataSourceType


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: DataSourceType
    config: dict = Field(default_factory=dict)
    sync_interval_minutes: int = Field(default=15, ge=1)


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=1)


class DataSourceResponse(BaseModel):
    id: str
    project_id: str
    name: str
    type: DataSourceType
    config: dict
    status: DataSourceStatus
    last_synced_at: datetime | None
    sync_interval_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceTestResult(BaseModel):
    success: bool
    message: str
    details: dict | None = None

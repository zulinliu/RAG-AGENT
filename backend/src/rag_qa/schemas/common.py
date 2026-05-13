from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


class PageData(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class PageResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: PageData[T] = Field(default_factory=PageData)


class ErrorDetail(BaseModel):
    code: str = "ERROR"
    message: str = "An error occurred"
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail = Field(default_factory=ErrorDetail)

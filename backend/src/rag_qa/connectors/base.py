from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class SyncResult(BaseModel):
    total: int = 0
    new: int = 0
    updated: int = 0
    deleted: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class FileMetadata(BaseModel):
    source_id: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    modified_at: datetime | None = None
    author: str | None = None
    checksum: str | None = None


class BaseConnector(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def list_changes(self, since: datetime | None = None) -> list[FileMetadata]:
        ...

    @abstractmethod
    async def download(self, file_metadata: FileMetadata, local_dir: str) -> str:
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        ...

    async def sync(self, since: datetime | None = None, local_dir: str = "/tmp/rag_qa/downloads") -> SyncResult:
        result = SyncResult()
        try:
            changes = await self.list_changes(since)
            result.total = len(changes)
            os.makedirs(local_dir, exist_ok=True)
            for file_meta in changes:
                try:
                    await self.download(file_meta, local_dir)
                    result.new += 1
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"{file_meta.file_path}: {e}")
        except Exception as e:
            result.errors.append(str(e))
        return result

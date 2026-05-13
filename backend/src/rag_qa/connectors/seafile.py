from __future__ import annotations

import mimetypes
import os
from datetime import datetime
from typing import Any

import httpx

from rag_qa.connectors.base import BaseConnector, FileMetadata

MAX_DEPTH = 10


class SeafileConnector(BaseConnector):
    def __init__(self, config: dict[str, Any]) -> None:
        self.server_url = config.get("server_url", "").rstrip("/")
        self.api_token = config.get("api_token", "")
        self.repo_id = config.get("repo_id", "")
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Token {self.api_token}"},
        )

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_changes(self, since: datetime | None = None) -> list[FileMetadata]:
        if self._client is None:
            raise RuntimeError("Not connected")
        results: list[FileMetadata] = []
        await self._walk_dir("/", results, since, 0)
        return results

    async def _walk_dir(
        self,
        path: str,
        results: list[FileMetadata],
        since: datetime | None,
        depth: int,
    ) -> None:
        if depth > MAX_DEPTH:
            return
        assert self._client is not None
        url = f"{self.server_url}/api/v2.1/repos/{self.repo_id}/dir/"
        resp = await self._client.get(url, params={"p": path})
        if resp.status_code != 200:
            raise RuntimeError(
                f"Seafile API error: {resp.status_code} {resp.text}"
            )
        entries = resp.json().get("dirent_list", [])
        for entry in entries:
            if entry.get("type") == "dir":
                child_path = path.rstrip("/") + "/" + entry["name"]
                await self._walk_dir(child_path, results, since, depth + 1)
            elif entry.get("type") == "file":
                mtime = entry.get("mtime", 0)
                if since is not None and mtime <= since.timestamp():
                    continue
                name = entry.get("name", "")
                parent_dir = entry.get("parent_dir", path)
                file_path = parent_dir.rstrip("/") + "/" + name
                mime_type, _ = mimetypes.guess_type(name)
                if mime_type is None:
                    mime_type = "application/octet-stream"
                results.append(
                    FileMetadata(
                        source_id=entry.get("oid", ""),
                        file_path=file_path,
                        file_name=name,
                        file_size=entry.get("size", 0),
                        mime_type=mime_type,
                        modified_at=datetime.fromtimestamp(mtime),
                    )
                )

    async def download(self, file_metadata: FileMetadata, local_dir: str) -> str:
        if self._client is None:
            raise RuntimeError("Not connected")
        os.makedirs(local_dir, exist_ok=True)
        url = f"{self.server_url}/api/v2.1/repos/{self.repo_id}/file/"
        resp = await self._client.get(
            url, params={"p": file_metadata.file_path, "download": "1"}
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Seafile download error: {resp.status_code} {resp.text}"
            )
        local_path = os.path.join(local_dir, file_metadata.file_name)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        return local_path

    async def test_connection(self) -> bool:
        if self._client is None:
            return False
        url = f"{self.server_url}/api/v2.1/repos/{self.repo_id}/"
        resp = await self._client.get(url)
        return resp.status_code == 200

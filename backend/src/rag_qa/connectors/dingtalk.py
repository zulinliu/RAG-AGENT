from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from rag_qa.connectors.base import BaseConnector, FileMetadata


class DingTalkAPIError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"DingTalk API error {code}: {message}")


class DingTalkConnector(BaseConnector):
    def __init__(self, config: dict) -> None:
        self.config = config
        self.app_key = config.get("app_key", "")
        self.app_secret = config.get("app_secret", "")
        self.dws_cli_path = config.get("dws_cli_path")
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        await self._get_access_token()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._access_token = None
        self._token_expires_at = 0.0

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 300:
            return self._access_token

        url = f"https://oapi.dingtalk.com/gettoken?appkey={self.app_key}&appsecret={self.app_secret}"
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

        resp = await self._client.post(url)
        data = resp.json()
        errcode = data.get("errcode", 0)
        if errcode != 0:
            raise DingTalkAPIError(errcode, data.get("errmsg", "unknown error"))

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        self._token_expires_at = now + expires_in
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}", "x-acs-dingtalk-access-token": self._access_token}

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

        token = await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())
        resp = await self._client.request(method, url, headers=headers, **kwargs)
        data = resp.json()

        if isinstance(data, dict):
            code = data.get("code") or data.get("errcode", 0)
            if code and code != 0 and code != "0":
                msg = data.get("message") or data.get("errmsg", "unknown error")
                raise DingTalkAPIError(int(code), msg)

        return data

    async def list_changes(self, since: datetime | None = None) -> list[FileMetadata]:
        if self.dws_cli_path:
            return await self._list_changes_dws(since)
        return await self._list_changes_api(since)

    async def _list_changes_api(self, since: datetime | None = None) -> list[FileMetadata]:
        spaces_data = await self._request("GET", "https://api.dingtalk.com/v1.0/doc/spaces")
        spaces = spaces_data.get("value", []) if isinstance(spaces_data, dict) else []
        if not spaces and isinstance(spaces_data, dict) and "spaces" in spaces_data:
            spaces = spaces_data["spaces"]

        results: list[FileMetadata] = []
        for space in spaces:
            space_id = space.get("id") or space.get("spaceId") or space.get("space_id", "")
            space_name = space.get("name") or space.get("spaceName") or space.get("space_name", "")

            docs_data = await self._request(
                "GET", f"https://api.dingtalk.com/v1.0/doc/spaces/{space_id}/docs"
            )
            docs = docs_data.get("value", []) if isinstance(docs_data, dict) else []
            if not docs and isinstance(docs_data, dict) and "docs" in docs_data:
                docs = docs_data["docs"]

            for doc in docs:
                doc_id = doc.get("id") or doc.get("docId") or doc.get("doc_id", "")
                doc_name = doc.get("name") or doc.get("title") or doc.get("docName") or doc.get("doc_name", "")
                modified_time_str = doc.get("modifiedTime") or doc.get("modified_time") or doc.get("gmtModified")
                modified_at = None
                if modified_time_str:
                    try:
                        modified_at = datetime.fromisoformat(modified_time_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        try:
                            modified_at = datetime.fromtimestamp(int(modified_time_str) / 1000, tz=timezone.utc)
                        except (ValueError, TypeError, OSError):
                            pass

                if since is not None and modified_at is not None:
                    since_aware = since
                    if since_aware.tzinfo is None:
                        since_aware = since_aware.replace(tzinfo=timezone.utc)
                    mod_aware = modified_at
                    if mod_aware.tzinfo is None:
                        mod_aware = mod_aware.replace(tzinfo=timezone.utc)
                    if mod_aware <= since_aware:
                        continue

                doc_type = doc.get("type") or doc.get("docType") or doc.get("doc_type", "")
                mime_type = self._resolve_mime_type(doc_type)

                file_meta = FileMetadata(
                    source_id=doc_id,
                    file_path=f"{space_name}/{doc_name}",
                    file_name=doc_name,
                    file_size=doc.get("size", 0),
                    mime_type=mime_type,
                    modified_at=modified_at,
                    author=doc.get("creator") or doc.get("author") or doc.get("creatorName"),
                )
                results.append(file_meta)

        return results

    async def _list_changes_dws(self, since: datetime | None = None) -> list[FileMetadata]:
        import asyncio

        cmd = [self.dws_cli_path, "doc", "search", "--query", "*", "--limit", "1000"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"dws command failed: {stderr.decode()}")

        data = json.loads(stdout.decode())
        items = data if isinstance(data, list) else data.get("items", data.get("docs", []))

        results: list[FileMetadata] = []
        for item in items:
            doc_id = item.get("id") or item.get("docId") or item.get("doc_id", "")
            doc_name = item.get("name") or item.get("title") or item.get("docName") or item.get("doc_name", "")
            space_name = item.get("spaceName") or item.get("space_name") or item.get("space", "")

            modified_at = None
            modified_time_str = item.get("modifiedTime") or item.get("modified_time") or item.get("gmtModified")
            if modified_time_str:
                try:
                    modified_at = datetime.fromisoformat(modified_time_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    try:
                        modified_at = datetime.fromtimestamp(int(modified_time_str) / 1000, tz=timezone.utc)
                    except (ValueError, TypeError, OSError):
                        pass

            if since is not None and modified_at is not None:
                since_aware = since
                if since_aware.tzinfo is None:
                    since_aware = since_aware.replace(tzinfo=timezone.utc)
                mod_aware = modified_at
                if mod_aware.tzinfo is None:
                    mod_aware = mod_aware.replace(tzinfo=timezone.utc)
                if mod_aware <= since_aware:
                    continue

            doc_type = item.get("type") or item.get("docType") or item.get("doc_type", "")
            mime_type = self._resolve_mime_type(doc_type)

            file_meta = FileMetadata(
                source_id=doc_id,
                file_path=f"{space_name}/{doc_name}" if space_name else doc_name,
                file_name=doc_name,
                file_size=item.get("size", 0),
                mime_type=mime_type,
                modified_at=modified_at,
                author=item.get("creator") or item.get("author") or item.get("creatorName"),
            )
            results.append(file_meta)

        return results

    @staticmethod
    def _resolve_mime_type(doc_type: str) -> str:
        mapping = {
            "doc": "application/vnd.dingtalk.doc",
            "sheet": "application/vnd.dingtalk.sheet",
            "slide": "application/vnd.dingtalk.slide",
            "file": "application/octet-stream",
            "wiki": "application/vnd.dingtalk.wiki",
            "mindmap": "application/vnd.dingtalk.mindmap",
        }
        return mapping.get(doc_type, "application/vnd.dingtalk.doc")

    async def download(self, file_metadata: FileMetadata, local_dir: str) -> str:
        os.makedirs(local_dir, exist_ok=True)

        if file_metadata.mime_type == "application/octet-stream":
            return await self._download_attachment(file_metadata, local_dir)

        return await self._download_doc(file_metadata, local_dir)

    async def _download_doc(self, file_metadata: FileMetadata, local_dir: str) -> str:
        doc_id = file_metadata.source_id
        data = await self._request("GET", f"https://api.dingtalk.com/v1.0/doc/docs/{doc_id}")

        content = ""
        if isinstance(data, dict):
            content = data.get("content") or data.get("htmlContent") or data.get("body", "")
            if isinstance(content, dict):
                content = content.get("value", "")
            if not content:
                content = data.get("text", "")

        safe_name = Path(file_metadata.file_name).stem
        local_path = os.path.join(local_dir, f"{safe_name}.html")
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(content)

        return local_path

    async def _download_attachment(self, file_metadata: FileMetadata, local_dir: str) -> str:
        doc_id = file_metadata.source_id
        data = await self._request("GET", f"https://api.dingtalk.com/v1.0/doc/docs/{doc_id}")

        download_url = ""
        if isinstance(data, dict):
            download_url = data.get("downloadUrl") or data.get("download_url") or data.get("url", "")

        if not download_url:
            local_path = os.path.join(local_dir, file_metadata.file_name)
            with open(local_path, "wb") as f:
                pass
            return local_path

        token = await self._get_access_token()
        headers = self._auth_headers()
        resp = await self._client.get(download_url, headers=headers)
        resp.raise_for_status()

        local_path = os.path.join(local_dir, file_metadata.file_name)
        with open(local_path, "wb") as f:
            f.write(resp.content)

        return local_path

    async def test_connection(self) -> bool:
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False

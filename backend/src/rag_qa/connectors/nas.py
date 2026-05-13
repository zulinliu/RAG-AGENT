from __future__ import annotations

import mimetypes
import os
import shutil
from datetime import datetime
from typing import Any

from rag_qa.connectors.base import BaseConnector, FileMetadata


class NASConnector(BaseConnector):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.protocol = config.get("protocol", "smb").lower()
        self.host = config.get("host", "")
        self.port = config.get("port")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.share_path = config.get("share_path", "")
        self.webdav_path = config.get("webdav_path", "")
        self.nfs_mount_point = config.get("nfs_mount_point", "")
        self._smb_conn: Any = None
        self._webdav_client: Any = None
        self._connected = False

    async def connect(self) -> None:
        if self.protocol == "smb":
            from smb.SMBConnection import SMBConnection  # type: ignore[import-untyped]

            port = self.port or 445
            self._smb_conn = SMBConnection(
                self.username,
                self.password,
                "rag_qa_client",
                self.host,
                use_ntlm_v2=True,
                port=port,
            )
            self._smb_conn.connect(self.host, port)
            self._connected = True
        elif self.protocol == "webdav":
            from webdav3.client import Client  # type: ignore[import-untyped]

            port = self.port or 443
            options = {
                "webdav_hostname": f"{self.host}:{port}",
                "webdav_root": self.webdav_path,
                "webdav_login": self.username,
                "webdav_password": self.password,
            }
            self._webdav_client = Client(options)
            self._connected = True
        elif self.protocol == "nfs":
            if not os.path.isdir(self.nfs_mount_point):
                raise FileNotFoundError(f"NFS mount point not found: {self.nfs_mount_point}")
            self._connected = True
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")

    async def disconnect(self) -> None:
        if self.protocol == "smb" and self._smb_conn is not None:
            try:
                self._smb_conn.close()
            except Exception:
                pass
            self._smb_conn = None
        elif self.protocol == "webdav":
            self._webdav_client = None
        self._connected = False

    def _smb_list_recursive(self, share_name: str, path: str, since: datetime | None = None) -> list[FileMetadata]:
        results: list[FileMetadata] = []
        try:
            entries = self._smb_conn.listPath(share_name, path)
        except Exception:
            return results
        for entry in entries:
            if entry.filename in (".", ".."):
                continue
            full_path = f"{path}/{entry.filename}" if path != "/" else f"/{entry.filename}"
            if entry.isDirectory:
                results.extend(self._smb_list_recursive(share_name, full_path, since))
            else:
                modified_at = datetime.fromtimestamp(entry.last_write_time)
                if since is not None and modified_at <= since:
                    continue
                rel_path = full_path.lstrip("/")
                mime_type, _ = mimetypes.guess_type(entry.filename)
                results.append(
                    FileMetadata(
                        source_id=full_path,
                        file_path=rel_path,
                        file_name=entry.filename,
                        file_size=entry.file_size,
                        mime_type=mime_type or "application/octet-stream",
                        modified_at=modified_at,
                    )
                )
        return results

    def _webdav_list_recursive(self, path: str, since: datetime | None = None) -> list[FileMetadata]:
        results: list[FileMetadata] = []
        try:
            entries = self._webdav_client.list(path)
        except Exception:
            return results
        for entry in entries:
            if entry in (path, path.rstrip("/") + "/"):
                continue
            if self._webdav_client.is_dir(entry):
                results.extend(self._webdav_list_recursive(entry, since))
            else:
                try:
                    info = self._webdav_client.info(entry)
                    modified_str = info.get("modified", "")
                    modified_at = datetime.fromisoformat(modified_str) if modified_str else None
                except Exception:
                    modified_at = None
                if since is not None and modified_at is not None and modified_at <= since:
                    continue
                file_name = entry.rstrip("/").split("/")[-1]
                rel_path = entry.lstrip("/")
                mime_type, _ = mimetypes.guess_type(file_name)
                file_size = 0
                try:
                    size_str = info.get("size", "0")
                    file_size = int(size_str)
                except Exception:
                    pass
                results.append(
                    FileMetadata(
                        source_id=entry,
                        file_path=rel_path,
                        file_name=file_name,
                        file_size=file_size,
                        mime_type=mime_type or "application/octet-stream",
                        modified_at=modified_at,
                    )
                )
        return results

    def _nfs_list_recursive(self, root: str, since: datetime | None = None) -> list[FileMetadata]:
        results: list[FileMetadata] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                modified_at = datetime.fromtimestamp(stat.st_mtime)
                if since is not None and modified_at <= since:
                    continue
                rel_path = os.path.relpath(full_path, root)
                mime_type, _ = mimetypes.guess_type(filename)
                results.append(
                    FileMetadata(
                        source_id=full_path,
                        file_path=rel_path,
                        file_name=filename,
                        file_size=stat.st_size,
                        mime_type=mime_type or "application/octet-stream",
                        modified_at=modified_at,
                    )
                )
        return results

    async def list_changes(self, since: datetime | None = None) -> list[FileMetadata]:
        if not self._connected:
            raise RuntimeError("Not connected")
        if self.protocol == "smb":
            stripped = self.share_path.lstrip("/")
            share_name = stripped.split("/")[0]
            sub_path = "/" + "/".join(stripped.split("/")[1:]) if "/" in stripped else "/"
            return self._smb_list_recursive(share_name, sub_path, since)
        elif self.protocol == "webdav":
            return self._webdav_list_recursive(self.webdav_path or "/", since)
        elif self.protocol == "nfs":
            return self._nfs_list_recursive(self.nfs_mount_point, since)
        return []

    async def download(self, file_metadata: FileMetadata, local_dir: str) -> str:
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, file_metadata.file_name)
        if self.protocol == "smb":
            share_name = self.share_path.lstrip("/").split("/")[0]
            fp = file_metadata.file_path
            remote_path = fp if fp.startswith("/") else "/" + fp
            with open(local_path, "wb") as f:
                self._smb_conn.retrieveFile(share_name, remote_path, f)
        elif self.protocol == "webdav":
            self._webdav_client.download_sync(remote_path=file_metadata.source_id, local_path=local_path)
        elif self.protocol == "nfs":
            src_path = os.path.join(self.nfs_mount_point, file_metadata.file_path)
            shutil.copy2(src_path, local_path)
        return local_path

    async def test_connection(self) -> bool:
        try:
            if self.protocol == "smb":
                if self._smb_conn is None:
                    return False
                self._smb_conn.listPath(self.share_path.lstrip("/").split("/")[0], "/")
                return True
            elif self.protocol == "webdav":
                if self._webdav_client is None:
                    return False
                self._webdav_client.list("/")
                return True
            elif self.protocol == "nfs":
                return os.path.isdir(self.nfs_mount_point) and os.access(self.nfs_mount_point, os.R_OK)
            return False
        except Exception:
            return False

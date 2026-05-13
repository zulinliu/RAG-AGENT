"""Seafile 连接器，通过 Web API v2.1 连接。"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base import BaseConnector, FileMetadata

logger = logging.getLogger(__name__)

# Seafile API 常量
API_TIMEOUT = 30


class SeafileConnector(BaseConnector):
    """Seafile 连接器。

    通过 Seafile Web API v2.1 连接，使用 Token 认证，
    支持递归遍历资料库目录和增量同步。
    """

    def __init__(
        self,
        server_url: str,
        token: str,
        repo_id: str,
        sync_dir: str = "/",
        allowed_extensions: Optional[set] = None,
        local_download_dir: Optional[str] = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.repo_id = repo_id
        self.sync_dir = sync_dir
        self.allowed_extensions = allowed_extensions
        self.local_download_dir = local_download_dir or tempfile.mkdtemp(prefix="seafile_")
        self._session: Optional[requests.Session] = None

    def connect(self) -> None:
        """建立连接，验证 Token 有效性。"""
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Token {self.token}"})
        # 验证连接
        resp = self._session.get(f"{self.server_url}/api2/auth/ping/", timeout=API_TIMEOUT)
        resp.raise_for_status()
        logger.info("Seafile 连接成功: %s", self.server_url)

    def disconnect(self) -> None:
        """断开连接。"""
        if self._session is not None:
            self._session.close()
            self._session = None
        logger.info("Seafile 连接已断开")

    def list_files(self, **kwargs: Any) -> List[FileMetadata]:
        """递归遍历资料库目录，返回所有文件元数据。"""
        if self._session is None:
            raise RuntimeError("未连接，请先调用 connect()")
        return self._list_dir_recursive(self.sync_dir)

    def download_file(self, file_path: str, local_dir: str) -> str:
        """下载文件到本地目录。"""
        if self._session is None:
            raise RuntimeError("未连接，请先调用 connect()")

        # 获取下载链接
        resp = self._session.get(
            f"{self.server_url}/api2/repos/{self.repo_id}/file/",
            params={"p": file_path},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        download_url = resp.json()

        # 下载文件
        file_resp = self._session.get(download_url, timeout=API_TIMEOUT * 3, stream=True)
        file_resp.raise_for_status()

        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / Path(file_path).name

        with open(str(dst_path), "wb") as f:
            for chunk in file_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("已下载: %s -> %s", file_path, dst_path)
        return str(dst_path)

    def get_file_metadata(self, file_path: str) -> FileMetadata:
        """获取文件元数据。"""
        if self._session is None:
            raise RuntimeError("未连接，请先调用 connect()")

        resp = self._session.get(
            f"{self.server_url}/api2/repos/{self.repo_id}/file/detail/",
            params={"p": file_path},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        detail = resp.json()

        return FileMetadata(
            file_path=file_path,
            file_size=detail.get("size", 0),
            mime_type=self._guess_mime(file_path),
            modified_at=datetime.fromtimestamp(detail.get("mtime", 0)),
            extra={"seafile_id": detail.get("id", "")},
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _list_dir_recursive(self, dir_path: str) -> List[FileMetadata]:
        """递归遍历目录。"""
        result: List[FileMetadata] = []
        resp = self._session.get(  # type: ignore[union-attr]
            f"{self.server_url}/api2/repos/{self.repo_id}/dir/",
            params={"p": dir_path},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        entries = resp.json()

        for entry in entries:
            entry_path = f"{dir_path.rstrip('/')}/{entry['name']}"
            if entry["type"] == "dir":
                result.extend(self._list_dir_recursive(entry_path))
            elif entry["type"] == "file":
                if self._is_allowed(entry["name"]):
                    result.append(FileMetadata(
                        file_path=entry_path,
                        file_size=entry.get("size", 0),
                        mime_type=self._guess_mime(entry["name"]),
                        modified_at=datetime.fromtimestamp(entry.get("mtime", 0)),
                        extra={"seafile_id": entry.get("id", "")},
                    ))
        return result

    def _is_allowed(self, filename: str) -> bool:
        """检查文件扩展名是否在白名单中。"""
        if self.allowed_extensions is None:
            return True
        return Path(filename).suffix.lower() in self.allowed_extensions

    @staticmethod
    def _guess_mime(file_path: str) -> str:
        """根据扩展名猜测 MIME 类型。"""
        import mimetypes

        mime, _ = mimetypes.guess_type(file_path)
        return mime or "application/octet-stream"

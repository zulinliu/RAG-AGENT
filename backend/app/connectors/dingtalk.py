"""钉钉知识库连接器，支持 API 模式和 CLI 模式。"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base import BaseConnector, FileMetadata

logger = logging.getLogger(__name__)

API_TIMEOUT = 30


class DingTalkConnector(BaseConnector):
    """钉钉知识库连接器。

    支持两种模式:
    - API 模式：通过 access_token 调用钉钉开放平台 API
    - CLI 模式：调用 dingtalk-workspace-cli 命令行工具
    """

    def __init__(
        self,
        mode: str = "api",
        # API 模式参数
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        agent_id: Optional[str] = None,
        # CLI 模式参数
        cli_path: Optional[str] = None,
        # 通用参数
        local_download_dir: Optional[str] = None,
    ) -> None:
        self.mode = mode.lower()
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id
        self.cli_path = cli_path or "dws"
        self.local_download_dir = local_download_dir or tempfile.mkdtemp(prefix="dingtalk_")
        self._session: Optional[requests.Session] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def connect(self) -> None:
        """建立连接。"""
        if self.mode == "api":
            self._connect_api()
        elif self.mode == "cli":
            self._connect_cli()
        else:
            raise ValueError(f"不支持的模式: {self.mode}，请使用 'api' 或 'cli'")

    def disconnect(self) -> None:
        """断开连接。"""
        if self._session is not None:
            self._session.close()
            self._session = None
        self._access_token = None
        logger.info("钉钉连接已断开 (%s)", self.mode)

    def list_files(self, **kwargs: Any) -> List[FileMetadata]:
        """列出知识库中的所有文档。"""
        if self.mode == "api":
            return self._list_api(kwargs.get("space_id", ""))
        elif self.mode == "cli":
            return self._list_cli(kwargs.get("space_id", ""))
        return []

    def download_file(self, file_path: str, local_dir: str) -> str:
        """下载文档内容到本地。"""
        if self.mode == "api":
            return self._download_api(file_path, local_dir)
        elif self.mode == "cli":
            return self._download_cli(file_path, local_dir)
        raise ValueError(f"不支持的模式: {self.mode}")

    def get_file_metadata(self, file_path: str) -> FileMetadata:
        """获取文档元数据。"""
        if self.mode == "api":
            return self._metadata_api(file_path)
        elif self.mode == "cli":
            return self._metadata_cli(file_path)
        raise ValueError(f"不支持的模式: {self.mode}")

    # ------------------------------------------------------------------
    # API 模式
    # ------------------------------------------------------------------

    def _connect_api(self) -> None:
        """API 模式：获取 access_token。"""
        if not self.app_key or not self.app_secret:
            raise ValueError("API 模式需要提供 app_key 和 app_secret")
        self._session = requests.Session()
        self._refresh_token()
        logger.info("钉钉 API 模式连接成功")

    def _refresh_token(self) -> None:
        """刷新 access_token。"""
        import time

        if time.time() < self._token_expires_at - 60:
            return  # 未过期，无需刷新

        url = "https://oapi.dingtalk.com/gettoken"
        params = {"appkey": self.app_key, "appsecret": self.app_secret}
        assert self._session is not None
        resp = self._session.get(url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode") != 0:
            raise RuntimeError(f"获取钉钉 token 失败: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)
        self._session.headers.update({"x-acs-dingtalk-access-token": self._access_token})
        logger.info("钉钉 access_token 已刷新")

    def _ensure_token(self) -> None:
        """确保 token 有效。"""
        import time

        if time.time() >= self._token_expires_at - 60:
            self._refresh_token()

    def _list_api(self, space_id: str) -> List[FileMetadata]:
        """API 模式：获取知识库文档列表。"""
        assert self._session is not None
        self._ensure_token()
        result: List[FileMetadata] = []

        url = f"https://api.dingtalk.com/v1.0/doc/spaces/{space_id}/docs"
        next_token = None

        while True:
            params: Dict[str, Any] = {"maxResults": 50}
            if next_token:
                params["nextToken"] = next_token
            resp = self._session.get(url, params=params, timeout=API_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            for doc in data.get("items", []):
                result.append(FileMetadata(
                    file_path=f"dingtalk://{space_id}/{doc['id']}",
                    file_size=0,
                    mime_type="text/markdown",
                    modified_at=datetime.fromisoformat(
                        doc.get("gmtModified", "1970-01-01T00:00:00+08:00")
                    ),
                    extra={"doc_id": doc["id"], "title": doc.get("title", "")},
                ))

            next_token = data.get("nextToken")
            if not next_token:
                break

        return result

    def _download_api(self, file_path: str, local_dir: str) -> str:
        """API 模式：下载文档内容。"""
        assert self._session is not None
        self._ensure_token()

        # 从 file_path 中解析 space_id 和 doc_id
        parts = file_path.replace("dingtalk://", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"无效的钉钉文档路径: {file_path}")
        space_id, doc_id = parts[0], parts[1]

        url = f"https://api.dingtalk.com/v1.0/doc/spaces/{space_id}/docs/{doc_id}"
        resp = self._session.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        title = data.get("title", doc_id)
        dst_path = dst_dir / f"{title}.md"

        content = data.get("content", "")
        with open(str(dst_path), "w", encoding="utf-8") as f:
            f.write(content)

        return str(dst_path)

    def _metadata_api(self, file_path: str) -> FileMetadata:
        """API 模式：获取文档元数据。"""
        assert self._session is not None
        self._ensure_token()

        parts = file_path.replace("dingtalk://", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"无效的钉钉文档路径: {file_path}")
        space_id, doc_id = parts[0], parts[1]

        url = f"https://api.dingtalk.com/v1.0/doc/spaces/{space_id}/docs/{doc_id}"
        resp = self._session.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        return FileMetadata(
            file_path=file_path,
            file_size=len(data.get("content", "").encode("utf-8")),
            mime_type="text/markdown",
            modified_at=datetime.fromisoformat(
                data.get("gmtModified", "1970-01-01T00:00:00+08:00")
            ),
            extra={"doc_id": doc_id, "title": data.get("title", "")},
        )

    # ------------------------------------------------------------------
    # CLI 模式
    # ------------------------------------------------------------------

    def _connect_cli(self) -> None:
        """CLI 模式：验证 dws 命令可用。"""
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"dws 命令执行失败: {result.stderr}")
            logger.info("钉钉 CLI 模式就绪: %s", self.cli_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"找不到 dingtalk-workspace-cli: {self.cli_path}，"
                "请确认已安装或指定正确路径"
            )

    def _list_cli(self, space_id: str) -> List[FileMetadata]:
        """CLI 模式：使用 dws 命令搜索文档。"""
        result = subprocess.run(
            [self.cli_path, "search", "--space-id", space_id, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("dws search 失败: %s", result.stderr)
            return []

        documents = json.loads(result.stdout)
        files: List[FileMetadata] = []
        for doc in documents:
            files.append(FileMetadata(
                file_path=f"dingtalk://{space_id}/{doc['id']}",
                file_size=0,
                mime_type="text/markdown",
                modified_at=datetime.fromisoformat(
                    doc.get("modified_at", "1970-01-01T00:00:00+08:00")
                ),
                extra={"doc_id": doc["id"], "title": doc.get("title", "")},
            ))
        return files

    def _download_cli(self, file_path: str, local_dir: str) -> str:
        """CLI 模式：使用 dws 命令下载文档。"""
        parts = file_path.replace("dingtalk://", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"无效的钉钉文档路径: {file_path}")
        space_id, doc_id = parts[0], parts[1]

        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                self.cli_path, "download",
                "--space-id", space_id,
                "--doc-id", doc_id,
                "--output-dir", str(dst_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"dws download 失败: {result.stderr}")

        # 查找下载的文件
        downloaded = list(dst_dir.glob(f"{doc_id}*"))
        if not downloaded:
            downloaded = list(dst_dir.glob("*"))
        if not downloaded:
            raise FileNotFoundError(f"下载文件未找到: {file_path}")

        return str(downloaded[0])

    def _metadata_cli(self, file_path: str) -> FileMetadata:
        """CLI 模式：获取文档元数据。"""
        parts = file_path.replace("dingtalk://", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"无效的钉钉文档路径: {file_path}")
        doc_id = parts[1]

        result = subprocess.run(
            [self.cli_path, "info", "--doc-id", doc_id, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"dws info 失败: {result.stderr}")

        info = json.loads(result.stdout)
        return FileMetadata(
            file_path=file_path,
            file_size=info.get("size", 0),
            mime_type="text/markdown",
            modified_at=datetime.fromisoformat(
                info.get("modified_at", "1970-01-01T00:00:00+08:00")
            ),
            extra={"doc_id": doc_id, "title": info.get("title", "")},
        )

"""NAS 连接器，支持 NFS 和 SMB 协议。"""

import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseConnector, FileMetadata

logger = logging.getLogger(__name__)

# 默认排除目录
DEFAULT_EXCLUDED_DIRS = {
    "__pycache__", ".git", "node_modules", ".idea", ".vscode",
    ".DS_Store", "Thumbs.db",
}


class NASConnector(BaseConnector):
    """NAS 连接器。

    支持 NFS（直接文件系统操作）和 SMB（使用 pysmb 库）两种模式。
    """

    def __init__(
        self,
        protocol: str = "nfs",
        host: Optional[str] = None,
        share_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        domain: str = "",
        mount_point: Optional[str] = None,
        remote_path: str = "/",
        allowed_extensions: Optional[set] = None,
        excluded_dirs: Optional[set] = None,
    ) -> None:
        self.protocol = protocol.lower()
        self.host = host
        self.share_name = share_name
        self.username = username
        self.password = password
        self.domain = domain
        self.mount_point = mount_point
        self.remote_path = remote_path
        self.allowed_extensions = allowed_extensions
        self.excluded_dirs = excluded_dirs or DEFAULT_EXCLUDED_DIRS
        self._smb_conn: Optional[Any] = None

    def connect(self) -> None:
        """建立连接。"""
        if self.protocol == "nfs":
            self._connect_nfs()
        elif self.protocol == "smb":
            self._connect_smb()
        else:
            raise ValueError(f"不支持的协议: {self.protocol}")

    def disconnect(self) -> None:
        """断开连接。"""
        if self.protocol == "smb" and self._smb_conn is not None:
            try:
                self._smb_conn.close()
            except Exception as e:
                logger.warning("关闭 SMB 连接失败: %s", e)
            self._smb_conn = None
        logger.info("NAS 连接已断开 (%s)", self.protocol)

    def list_files(self, **kwargs: Any) -> List[FileMetadata]:
        """列出所有可同步的文件。"""
        if self.protocol == "nfs":
            return self._list_nfs()
        elif self.protocol == "smb":
            return self._list_smb()
        return []

    def download_file(self, file_path: str, local_dir: str) -> str:
        """下载文件到本地目录。"""
        if self.protocol == "nfs":
            return self._download_nfs(file_path, local_dir)
        elif self.protocol == "smb":
            return self._download_smb(file_path, local_dir)
        raise ValueError(f"不支持的协议: {self.protocol}")

    def get_file_metadata(self, file_path: str) -> FileMetadata:
        """获取文件元数据。"""
        if self.protocol == "nfs":
            return self._metadata_nfs(file_path)
        elif self.protocol == "smb":
            return self._metadata_smb(file_path)
        raise ValueError(f"不支持的协议: {self.protocol}")

    # ------------------------------------------------------------------
    # NFS 实现
    # ------------------------------------------------------------------

    def _connect_nfs(self) -> None:
        """NFS 模式：验证挂载点。"""
        if self.mount_point is None:
            raise ValueError("NFS 模式需要指定 mount_point")
        mount_path = Path(self.mount_point)
        if not mount_path.exists():
            raise FileNotFoundError(f"NFS 挂载点不存在: {mount_path}")
        logger.info("NFS 连接就绪: %s", self.mount_point)

    def _list_nfs(self) -> List[FileMetadata]:
        """NFS 模式：递归遍历文件系统。"""
        base = Path(self.mount_point) / self.remote_path.lstrip("/")
        result: List[FileMetadata] = []
        for root, dirs, filenames in os.walk(str(base)):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for fname in filenames:
                p = Path(root) / fname
                if self._is_allowed(fname):
                    meta = self._metadata_nfs(str(p))
                    result.append(meta)
        return result

    def _download_nfs(self, file_path: str, local_dir: str) -> str:
        """NFS 模式：直接复制文件。"""
        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / Path(file_path).name
        shutil.copy2(file_path, str(dst))
        return str(dst)

    def _metadata_nfs(self, file_path: str) -> FileMetadata:
        """NFS 模式：获取文件元数据。"""
        p = Path(file_path)
        stat = p.stat()
        return FileMetadata(
            file_path=str(p),
            file_size=stat.st_size,
            mime_type=self._guess_mime(file_path),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
        )

    # ------------------------------------------------------------------
    # SMB 实现
    # ------------------------------------------------------------------

    def _connect_smb(self) -> None:
        """SMB 模式：使用 pysmb 建立连接。"""
        try:
            from smb.SMBConnection import SMBConnection
        except ImportError:
            raise ImportError("SMB 模式需要安装 pysmb 库: pip install pysmb")

        local_name = "rag-agent"
        server_name = (self.host or "").split(".")[0]
        self._smb_conn = SMBConnection(
            self.username or "",
            self.password or "",
            local_name,
            server_name,
            domain=self.domain,
            use_ntlm_v2=True,
        )
        assert self._smb_conn is not None
        connected = self._smb_conn.connect(self.host or "", 445)
        if not connected:
            raise ConnectionError(f"SMB 连接失败: {self.host}")
        logger.info("SMB 连接成功: %s/%s", self.host, self.share_name)

    def _list_smb(self) -> List[FileMetadata]:
        """SMB 模式：递归遍历共享目录。"""
        assert self._smb_conn is not None
        result: List[FileMetadata] = []
        self._walk_smb(self.remote_path, result)
        return result

    def _walk_smb(self, path: str, result: List[FileMetadata]) -> None:
        """递归遍历 SMB 目录。"""
        assert self._smb_conn is not None
        assert self.share_name is not None
        entries = self._smb_conn.listPath(self.share_name, path)
        for entry in entries:
            if entry.filename in (".", ".."):
                continue
            entry_path = f"{path.rstrip('/')}/{entry.filename}"
            if entry.isDirectory:
                if entry.filename not in self.excluded_dirs:
                    self._walk_smb(entry_path, result)
            else:
                if self._is_allowed(entry.filename):
                    result.append(FileMetadata(
                        file_path=entry_path,
                        file_size=entry.file_size,
                        mime_type=self._guess_mime(entry.filename),
                        modified_at=datetime.fromtimestamp(
                            entry.last_write_time if hasattr(entry, "last_write_time") else 0
                        ),
                    ))

    def _download_smb(self, file_path: str, local_dir: str) -> str:
        """SMB 模式：下载文件。"""
        assert self._smb_conn is not None
        assert self.share_name is not None

        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = dst_dir / Path(file_path).name

        with open(str(dst_path), "wb") as f:
            self._smb_conn.retrieveFile(self.share_name, file_path, f)
        return str(dst_path)

    def _metadata_smb(self, file_path: str) -> FileMetadata:
        """SMB 模式：获取文件元数据。"""
        assert self._smb_conn is not None
        assert self.share_name is not None
        attrs = self._smb_conn.getAttributes(self.share_name, file_path)
        return FileMetadata(
            file_path=file_path,
            file_size=attrs.file_size,
            mime_type=self._guess_mime(file_path),
            modified_at=datetime.fromtimestamp(
                attrs.last_write_time if hasattr(attrs, "last_write_time") else 0
            ),
        )

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------

    def _is_allowed(self, filename: str) -> bool:
        """检查文件扩展名。"""
        if self.allowed_extensions is None:
            return True
        return Path(filename).suffix.lower() in self.allowed_extensions

    @staticmethod
    def _guess_mime(file_path: str) -> str:
        """猜测 MIME 类型。"""
        import mimetypes

        mime, _ = mimetypes.guess_type(file_path)
        return mime or "application/octet-stream"

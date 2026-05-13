"""本地文件系统连接器，支持 watchdog 目录监控。"""

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import BaseConnector, FileMetadata

logger = logging.getLogger(__name__)

# 支持的文件扩展名白名单
DEFAULT_ALLOWED_EXTENSIONS: Set[str] = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".md", ".txt", ".png", ".jpg",
}

# 默认排除目录
DEFAULT_EXCLUDED_DIRS: Set[str] = {
    "__pycache__", ".git", "node_modules", ".idea", ".vscode",
    ".venv", "venv", ".tox", ".mypy_cache",
}


class LocalConnector(BaseConnector):
    """本地文件系统连接器。

    使用 watchdog 监控指定目录的文件创建/修改/删除事件，
    支持配置文件扩展名白名单和排除目录。
    """

    def __init__(
        self,
        watch_dir: str,
        allowed_extensions: Optional[Set[str]] = None,
        excluded_dirs: Optional[Set[str]] = None,
    ) -> None:
        self.watch_dir = Path(watch_dir).resolve()
        self.allowed_extensions = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
        self.excluded_dirs = excluded_dirs or DEFAULT_EXCLUDED_DIRS
        self._observer: Optional[Any] = None
        self._watching = False
        self._watch_thread: Optional[threading.Thread] = None

    def connect(self) -> None:
        """建立连接（本地文件系统无需特殊连接）。"""
        if not self.watch_dir.exists():
            raise FileNotFoundError(f"监控目录不存在: {self.watch_dir}")
        logger.info("本地连接器就绪，监控目录: %s", self.watch_dir)

    def disconnect(self) -> None:
        """断开连接，停止监控。"""
        self.stop_watching()

    def list_files(self, **kwargs: Any) -> List[FileMetadata]:
        """列出所有可同步的文件。"""
        result: List[FileMetadata] = []
        for file_path in self._iter_files():
            meta = self.get_file_metadata(str(file_path))
            if meta is not None:
                result.append(meta)
        return result

    def download_file(self, file_path: str, local_dir: str) -> str:
        """本地文件直接复制到目标目录。"""
        import shutil

        src = Path(file_path)
        dst_dir = Path(local_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.copy2(str(src), str(dst))
        return str(dst)

    def get_file_metadata(self, file_path: str) -> Optional[FileMetadata]:
        """获取文件元数据。"""
        p = Path(file_path)
        if not p.exists():
            return None
        stat = p.stat()
        mime_type = self._guess_mime(p)
        return FileMetadata(
            file_path=str(p),
            file_size=stat.st_size,
            mime_type=mime_type,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            checksum=None,
        )

    def start_watching(self) -> None:
        """启动后台监控线程。"""
        if self._watching:
            return
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent

            class Handler(FileSystemEventHandler):
                def __init__(self, connector: "LocalConnector") -> None:
                    self.connector = connector

                def on_created(self, event: Any) -> None:
                    if not event.is_directory:
                        logger.info("文件创建: %s", event.src_path)

                def on_modified(self, event: Any) -> None:
                    if not event.is_directory:
                        logger.info("文件修改: %s", event.src_path)

                def on_deleted(self, event: Any) -> None:
                    if not event.is_directory:
                        logger.info("文件删除: %s", event.src_path)

            self._observer = Observer()
            self._observer.schedule(Handler(self), str(self.watch_dir), recursive=True)
            self._observer.daemon = True
            self._observer.start()
            self._watching = True
            logger.info("已启动目录监控: %s", self.watch_dir)
        except ImportError:
            logger.warning("watchdog 未安装，目录监控不可用")
        except Exception as e:
            logger.error("启动监控失败: %s", e)

    def stop_watching(self) -> None:
        """停止监控。"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._watching = False
        logger.info("已停止目录监控")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _iter_files(self) -> List[Path]:
        """递归遍历目录，返回所有符合条件的文件。"""
        files: List[Path] = []
        for root, dirs, filenames in os.walk(str(self.watch_dir)):
            # 跳过排除目录
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for fname in filenames:
                p = Path(root) / fname
                if p.suffix.lower() in self.allowed_extensions:
                    files.append(p)
        return files

    @staticmethod
    def _guess_mime(path: Path) -> str:
        """根据扩展名猜测 MIME 类型。"""
        import mimetypes

        mime, _ = mimetypes.guess_type(str(path))
        return mime or "application/octet-stream"

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
from collections.abc import Callable
from datetime import datetime
from fnmatch import fnmatch
from typing import Any

from rag_qa.connectors.base import BaseConnector, FileMetadata


class LocalConnector(BaseConnector):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.base_path = config.get("base_path", "")
        self.watch_patterns = config.get("watch_patterns", ["*"])
        self._connected = False
        self._observer: Any = None

    def _matches_pattern(self, filename: str) -> bool:
        for pattern in self.watch_patterns:
            if fnmatch(filename, pattern):
                return True
        return False

    async def connect(self) -> None:
        if not os.path.isdir(self.base_path):
            raise FileNotFoundError(f"Base path not found: {self.base_path}")
        if not os.access(self.base_path, os.R_OK):
            raise PermissionError(f"Base path not readable: {self.base_path}")
        self._connected = True

    async def disconnect(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._connected = False

    async def list_changes(self, since: datetime | None = None) -> list[FileMetadata]:
        if not self._connected:
            raise RuntimeError("Not connected")
        results: list[FileMetadata] = []
        for dirpath, _dirnames, filenames in os.walk(self.base_path):
            for filename in filenames:
                if not self._matches_pattern(filename):
                    continue
                full_path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                modified_at = datetime.fromtimestamp(stat.st_mtime)
                if since is not None and modified_at <= since:
                    continue
                rel_path = os.path.relpath(full_path, self.base_path)
                source_id = hashlib.sha256(full_path.encode("utf-8")).hexdigest()
                mime_type, _ = mimetypes.guess_type(filename)
                results.append(
                    FileMetadata(
                        source_id=source_id,
                        file_path=rel_path,
                        file_name=filename,
                        file_size=stat.st_size,
                        mime_type=mime_type or "application/octet-stream",
                        modified_at=modified_at,
                    )
                )
        return results

    async def download(self, file_metadata: FileMetadata, local_dir: str) -> str:
        os.makedirs(local_dir, exist_ok=True)
        src_path = os.path.join(self.base_path, file_metadata.file_path)
        local_path = os.path.join(local_dir, file_metadata.file_name)
        shutil.copy2(src_path, local_path)
        return local_path

    async def test_connection(self) -> bool:
        return os.path.isdir(self.base_path) and os.access(self.base_path, os.R_OK)

    def start_watching(self, callback: Callable[[str, str], None]) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class _Handler(FileSystemEventHandler):
            def __init__(self, patterns: list[str], cb: Callable[[str, str], None]) -> None:
                super().__init__()
                self.patterns = patterns
                self.cb = cb

            def _matches(self, filename: str) -> bool:
                for p in self.patterns:
                    if fnmatch(filename, p):
                        return True
                return False

            def on_created(self, event: Any) -> None:
                if not event.is_directory and self._matches(os.path.basename(event.src_path)):
                    self.cb("created", event.src_path)

            def on_modified(self, event: Any) -> None:
                if not event.is_directory and self._matches(os.path.basename(event.src_path)):
                    self.cb("modified", event.src_path)

            def on_deleted(self, event: Any) -> None:
                if not event.is_directory and self._matches(os.path.basename(event.src_path)):
                    self.cb("deleted", event.src_path)

        handler = _Handler(self.watch_patterns, callback)
        self._observer = Observer()
        self._observer.schedule(handler, self.base_path, recursive=True)
        self._observer.start()

    def stop_watching(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

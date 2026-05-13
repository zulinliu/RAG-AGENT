"""连接器基类和数据模型。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SyncTask:
    """同步任务数据模型。"""

    source: str
    file_path: str
    project_id: str
    data_source_id: str
    file_size: int
    mime_type: str
    modified_at: datetime
    checksum: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileMetadata:
    """文件元数据。"""

    file_path: str
    file_size: int
    mime_type: str
    modified_at: datetime
    checksum: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """数据源连接器基类。"""

    @abstractmethod
    def connect(self) -> None:
        """建立连接。"""

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接。"""

    @abstractmethod
    def list_files(self, **kwargs: Any) -> List[FileMetadata]:
        """列出所有可同步的文件。"""

    @abstractmethod
    def download_file(self, file_path: str, local_dir: str) -> str:
        """下载文件到本地目录，返回本地文件路径。"""

    @abstractmethod
    def get_file_metadata(self, file_path: str) -> FileMetadata:
        """获取文件元数据。"""

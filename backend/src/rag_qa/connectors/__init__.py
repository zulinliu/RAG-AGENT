from __future__ import annotations

from rag_qa.connectors.base import BaseConnector, FileMetadata, SyncResult
from rag_qa.connectors.dingtalk import DingTalkConnector
from rag_qa.connectors.local import LocalConnector
from rag_qa.connectors.nas import NASConnector
from rag_qa.connectors.registry import ConnectorRegistry, registry
from rag_qa.connectors.seafile import SeafileConnector
from rag_qa.schemas.metadata import SourceType

registry.register(SourceType.DINGTALK, DingTalkConnector)
registry.register(SourceType.SEAFILE, SeafileConnector)
registry.register(SourceType.NAS, NASConnector)
registry.register(SourceType.LOCAL, LocalConnector)

__all__ = [
    "BaseConnector",
    "FileMetadata",
    "SyncResult",
    "ConnectorRegistry",
    "registry",
    "DingTalkConnector",
    "SeafileConnector",
    "NASConnector",
    "LocalConnector",
]

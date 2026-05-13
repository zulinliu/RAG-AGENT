from __future__ import annotations

from rag_qa.connectors.base import BaseConnector
from rag_qa.schemas.metadata import SourceType


class ConnectorRegistry:
    def __init__(self) -> None:
        self._registry: dict[SourceType, type[BaseConnector]] = {}

    def register(self, source_type: SourceType, connector_class: type[BaseConnector]) -> None:
        self._registry[source_type] = connector_class

    def get_connector(self, source_type: SourceType, config: dict) -> BaseConnector:
        connector_class = self._registry.get(source_type)
        if connector_class is None:
            raise ValueError(f"No connector registered for source type: {source_type}")
        return connector_class(config)


registry = ConnectorRegistry()

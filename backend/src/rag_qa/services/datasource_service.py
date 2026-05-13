from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.connectors.registry import registry
from rag_qa.core.exceptions import ConnectorException, NotFoundException
from rag_qa.models.datasource import DataSource
from rag_qa.models.sync import SyncTask
from rag_qa.schemas.datasource import DataSourceCreate, DataSourceTestResult, DataSourceUpdate
from rag_qa.services.sync_service import SyncService


class DataSourceService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def create(self, project_id: str, data: DataSourceCreate) -> DataSource:
        datasource = DataSource(
            project_id=project_id,
            name=data.name,
            type=data.type,
            config=data.config,
            sync_interval_minutes=data.sync_interval_minutes,
        )
        self.db.add(datasource)
        await self.db.commit()
        await self.db.refresh(datasource)
        return datasource

    async def update(self, datasource_id: str, data: DataSourceUpdate) -> DataSource:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")

        if data.name is not None:
            datasource.name = data.name
        if data.config is not None:
            datasource.config = data.config
        if data.sync_interval_minutes is not None:
            datasource.sync_interval_minutes = data.sync_interval_minutes

        await self.db.commit()
        await self.db.refresh(datasource)
        return datasource

    async def delete(self, datasource_id: str) -> None:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")

        await self.db.delete(datasource)
        await self.db.commit()

    async def get(self, datasource_id: str) -> DataSource:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")
        return datasource

    async def list_by_project(self, project_id: str) -> list[DataSource]:
        stmt = select(DataSource).where(DataSource.project_id == project_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def test_connection(self, datasource_id: str) -> DataSourceTestResult:
        datasource = await self.db.get(DataSource, datasource_id)
        if datasource is None:
            raise NotFoundException(f"DataSource {datasource_id} not found")

        connector = None
        try:
            source_type = datasource.type.value
            connector = registry.get_connector(source_type, datasource.config)
            await connector.connect()
            success = await connector.test_connection()
            return DataSourceTestResult(
                success=success,
                message="Connection successful" if success else "Connection test failed",
            )
        except Exception as e:
            return DataSourceTestResult(
                success=False,
                message=f"Connection failed: {e}",
                details={"error": str(e)},
            )
        finally:
            if connector is not None:
                try:
                    await connector.disconnect()
                except Exception:
                    pass

    async def trigger_sync(self, datasource_id: str) -> SyncTask:
        sync_service = SyncService(self.db)
        return await sync_service.trigger_sync(datasource_id)

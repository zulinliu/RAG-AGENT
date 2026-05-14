"""双索引构建器，同时写入 Milvus 和 Elasticsearch。"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DualIndexer:
    """双索引构建器。

    同时写入 Milvus（向量索引）和 Elasticsearch（全文索引），
    并在 PostgreSQL 中记录文档元数据和同步状态。
    """

    def __init__(
        self,
        # Milvus 配置
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        milvus_collection: str = "rag_chunks",
        # Elasticsearch 配置
        es_hosts: Optional[List[str]] = None,
        es_index_prefix: str = "rag",
        # PostgreSQL 配置
        pg_dsn: Optional[str] = None,
        # 向量维度
        vector_dim: int = 1024,
    ) -> None:
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.milvus_collection = milvus_collection
        self.es_hosts = es_hosts or ["http://localhost:9200"]
        self.es_index_prefix = es_index_prefix
        self.pg_dsn = pg_dsn
        self.vector_dim = vector_dim
        self._milvus: Optional[Any] = None
        self._es: Optional[Any] = None
        self._pg_pool: Optional[Any] = None

    def connect(self) -> None:
        """建立所有连接。"""
        self._connect_milvus()
        self._connect_es()
        self._connect_pg()

    def disconnect(self) -> None:
        """断开所有连接。"""
        if self._milvus is not None:
            from pymilvus import connections
            connections.disconnect("default")
            self._milvus = None
        if self._es is not None:
            self._es.close()  # type: ignore[union-attr]
            self._es = None
        if self._pg_pool is not None:
            self._pg_pool.close()  # type: ignore[union-attr]
            self._pg_pool = None
        logger.info("DualIndexer 所有连接已断开")

    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
        project_id: str,
        document_id: str,
        data_source_id: str,
    ) -> int:
        """将分块和向量写入双索引（原子性保证）。

        先将文档状态标记为 indexing，两个索引都成功后标记为 indexed，
        任一失败时清理已成功的那个并标记为 error。

        Args:
            chunks: 分块列表，每个包含 content 和 metadata
            vectors: 对应的向量列表
            project_id: 项目 ID
            document_id: 文档 ID
            data_source_id: 数据源 ID

        Returns:
            成功索引的分块数量
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"chunks({len(chunks)}) 和 vectors({len(vectors)}) 数量不匹配")

        if not chunks:
            return 0

        # 标记文档状态为 indexing
        self._set_document_status(document_id, project_id, data_source_id, "indexing")

        milvus_ids: List[str] = []
        es_count = 0

        try:
            # 写入 Milvus
            milvus_ids = self._write_milvus(chunks, vectors, project_id, document_id)
            logger.info("Milvus 写入完成: %d 条", len(milvus_ids))
        except Exception as e:
            logger.error("Milvus 写入失败: %s", e)

        try:
            # 写入 Elasticsearch
            es_count = self._write_es(chunks, project_id, document_id)
            logger.info("Elasticsearch 写入完成: %d 条", es_count)
        except Exception as e:
            logger.error("Elasticsearch 写入失败: %s", e)
            # Milvus 成功但 ES 失败，清理 Milvus
            if milvus_ids:
                logger.warning("ES 写入失败，回滚 Milvus 写入")
                try:
                    self._delete_from_milvus(document_id)
                except Exception as rollback_err:
                    logger.error("Milvus 回滚失败: %s", rollback_err)
            self._set_document_status(document_id, project_id, data_source_id, "error", str(e))
            return 0

        if not milvus_ids:
            # ES 成功但 Milvus 失败，清理 ES
            if es_count > 0:
                logger.warning("Milvus 写入失败，回滚 ES 写入")
                try:
                    self._delete_from_es(document_id)
                except Exception as rollback_err:
                    logger.error("ES 回滚失败: %s", rollback_err)
            self._set_document_status(document_id, project_id, data_source_id, "error", "Milvus write failed")
            return 0

        # 两个索引都成功，更新 PostgreSQL 元数据
        try:
            self._update_pg_metadata(chunks, project_id, document_id, data_source_id)
            logger.info("PostgreSQL 元数据更新完成")
        except Exception as e:
            logger.error("PostgreSQL 更新失败: %s", e)
            # 索引已写入，不回滚，仅记录错误
            self._set_document_status(document_id, project_id, data_source_id, "error", str(e))

        return len(milvus_ids)

    def _set_document_status(
        self,
        document_id: str,
        project_id: str,
        data_source_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """更新 PostgreSQL 中的文档状态。"""
        if self._pg_pool is None:
            return
        try:
            with self._pg_pool.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO documents (id, project_id, data_source_id, file_path, status, error_message, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        updated_at = NOW()
                    """,
                    (document_id, project_id, data_source_id, "", status, error_message),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to set document status: %s", e)

    def delete_document(self, document_id: str) -> bool:
        """从所有索引中删除文档。"""
        # 验证 document_id 为有效 UUID 格式，防止 filter 表达式注入
        try:
            uuid.UUID(document_id)
        except ValueError:
            raise ValueError(f"Invalid document_id format (expected UUID): {document_id!r}")

        success = True

        # 从 Milvus 删除
        try:
            self._delete_from_milvus(document_id)
        except Exception as e:
            logger.error("从 Milvus 删除失败: %s", e)
            success = False

        # 从 ES 删除
        try:
            self._delete_from_es(document_id)
        except Exception as e:
            logger.error("从 ES 删除失败: %s", e)
            success = False

        # 从 PG 删除
        try:
            self._delete_from_pg(document_id)
        except Exception as e:
            logger.error("从 PG 删除失败: %s", e)
            success = False

        return success

    # ------------------------------------------------------------------
    # Milvus 操作
    # ------------------------------------------------------------------

    def _connect_milvus(self) -> None:
        """连接 Milvus。"""
        try:
            from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType

            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port,
            )
            self._ensure_milvus_collection()
            self._milvus = Collection(self.milvus_collection)
            logger.info("Milvus 连接成功: %s:%d", self.milvus_host, self.milvus_port)
        except ImportError:
            logger.warning("pymilvus 未安装，Milvus 功能不可用")
        except Exception as e:
            logger.error("Milvus 连接失败: %s", e)

    def _ensure_milvus_collection(self) -> None:
        """确保 Milvus 集合存在（统一 schema，与 config/milvus/collection.py 保持一致）。"""
        from pymilvus import utility, Collection, FieldSchema, CollectionSchema, DataType

        if utility.has_collection(self.milvus_collection):
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="project_id", dtype=DataType.VARCHAR, max_length=64, is_partition_key=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="parent_title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="hierarchy", dtype=DataType.JSON),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
        ]
        schema = CollectionSchema(fields=fields, description="RAG chunks")
        collection = Collection(name=self.milvus_collection, schema=schema)

        # 创建 HNSW 索引（与 config/milvus/collection.py 一致）
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 128},
        }
        collection.create_index(field_name="vector", index_params=index_params)
        collection.load()
        logger.info("Milvus 集合已创建 (HNSW): %s", self.milvus_collection)

    def _write_milvus(
        self,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
        project_id: str,
        document_id: str,
    ) -> List[str]:
        """写入 Milvus。"""
        if self._milvus is None:
            return []

        ids = []
        doc_ids = []
        project_ids = []
        contents = []
        chunk_types = []
        parent_titles = []
        hierarchies = []

        for i, (chunk, _vec) in enumerate(zip(chunks, vectors)):
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            doc_ids.append(document_id)
            project_ids.append(project_id)
            contents.append(chunk.get("content", "")[:8192])
            chunk_types.append(chunk.get("metadata", {}).get("chunk_type", "paragraph"))
            parent_titles.append(chunk.get("metadata", {}).get("parent_title", "")[:512])
            hierarchies.append(chunk.get("metadata", {}).get("hierarchy", []))

        entities = [ids, project_ids, doc_ids, contents, chunk_types, parent_titles, hierarchies, vectors]
        self._milvus.insert(entities)
        self._milvus.flush()
        return ids

    def _delete_from_milvus(self, document_id: str) -> None:
        """从 Milvus 删除文档。"""
        if self._milvus is None:
            return
        # document_id 已在 delete_document 中通过 UUID 验证
        validated_id = str(uuid.UUID(document_id))
        expr = f'document_id == "{validated_id}"'
        self._milvus.delete(expr)
        self._milvus.flush()

    # ------------------------------------------------------------------
    # Elasticsearch 操作
    # ------------------------------------------------------------------

    def _connect_es(self) -> None:
        """连接 Elasticsearch。"""
        try:
            from elasticsearch import Elasticsearch

            self._es = Elasticsearch(self.es_hosts)
            self._ensure_es_index()
            logger.info("Elasticsearch 连接成功: %s", self.es_hosts)
        except ImportError:
            logger.warning("elasticsearch 未安装，ES 功能不可用")
        except Exception as e:
            logger.error("Elasticsearch 连接失败: %s", e)

    def _ensure_es_index(self) -> None:
        """确保 ES 索引存在。"""
        assert self._es is not None
        index_name = f"{self.es_index_prefix}_chunks"

        if self._es.indices.exists(index=index_name):
            return

        mapping = {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "ik_smart_analyzer": {
                            "type": "custom",
                            "tokenizer": "ik_max_word",
                        },
                    },
                },
            },
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "project_id": {"type": "keyword"},
                    "data_source_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "content": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                    },
                    "chunk_type": {"type": "keyword"},
                    "parent_title": {"type": "text", "analyzer": "ik_max_word"},
                    "hierarchy": {"type": "keyword"},
                    "char_count": {"type": "integer"},
                    "created_at": {"type": "date"},
                },
            },
        }
        self._es.indices.create(index=index_name, body=mapping)
        logger.info("ES 索引已创建: %s", index_name)

    def _write_es(
        self,
        chunks: List[Dict[str, Any]],
        project_id: str,
        document_id: str,
    ) -> int:
        """写入 Elasticsearch（使用 bulk API 批量索引）。"""
        if self._es is None:
            return 0

        from elasticsearch.helpers import bulk

        index_name = f"{self.es_index_prefix}_chunks"

        def _gen_actions() -> Any:
            for i, chunk in enumerate(chunks):
                yield {
                    "_index": index_name,
                    "_source": {
                        "document_id": document_id,
                        "project_id": project_id,
                        "chunk_index": i,
                        "content": chunk.get("content", ""),
                        "chunk_type": chunk.get("metadata", {}).get("chunk_type", "paragraph"),
                        "parent_title": chunk.get("metadata", {}).get("parent_title", ""),
                        "hierarchy": chunk.get("metadata", {}).get("hierarchy", ""),
                        "char_count": len(chunk.get("content", "")),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                }

        success, _errors = bulk(self._es, _gen_actions(), refresh=True)
        return success

    def _delete_from_es(self, document_id: str) -> None:
        """从 ES 删除文档。"""
        if self._es is None:
            return
        index_name = f"{self.es_index_prefix}_chunks"
        self._es.delete_by_query(
            index=index_name,
            body={"query": {"term": {"document_id": document_id}}},
        )

    # ------------------------------------------------------------------
    # PostgreSQL 操作
    # ------------------------------------------------------------------

    def _connect_pg(self) -> None:
        """连接 PostgreSQL。

        Schema management is handled by Alembic migrations, not by this module.
        """
        if self.pg_dsn is None:
            logger.info("未配置 PostgreSQL DSN，跳过 PG 连接")
            return
        try:
            import psycopg_pool

            self._pg_pool = psycopg_pool.ConnectionPool(
                self.pg_dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("PostgreSQL 连接成功")
        except ImportError:
            logger.warning("psycopg 未安装，PG 功能不可用")
        except Exception as e:
            logger.error("PostgreSQL 连接失败: %s", e)

    def _update_pg_metadata(
        self,
        chunks: List[Dict[str, Any]],
        project_id: str,
        document_id: str,
        data_source_id: str,
    ) -> None:
        """更新 PostgreSQL 中的文档元数据。"""
        if self._pg_pool is None:
            return

        with self._pg_pool.connection() as conn:
            # 更新文档状态
            conn.execute(
                """
                INSERT INTO documents (id, project_id, data_source_id, file_path, chunk_count, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'indexed', NOW())
                ON CONFLICT (id) DO UPDATE SET
                    chunk_count = EXCLUDED.chunk_count,
                    status = 'indexed',
                    updated_at = NOW()
                """,
                (document_id, project_id, data_source_id, "", len(chunks)),
            )

            # 写入分块信息
            for i, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO chunks (id, document_id, project_id, chunk_index, content, char_count, parent_title, hierarchy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        chunk_id,
                        document_id,
                        project_id,
                        i,
                        chunk.get("content", ""),
                        len(chunk.get("content", "")),
                        chunk.get("metadata", {}).get("parent_title", ""),
                        chunk.get("metadata", {}).get("hierarchy", ""),
                    ),
                )

            conn.commit()

    def _delete_from_pg(self, document_id: str) -> None:
        """从 PG 删除文档及其分块。"""
        if self._pg_pool is None:
            return
        with self._pg_pool.connection() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            conn.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            conn.commit()

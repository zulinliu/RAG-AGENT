"""去重工具：精确去重（SHA-256）和模糊去重（向量相似度）。"""

import hashlib
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: str) -> str:
    """计算文件的 SHA-256 哈希值。

    Args:
        file_path: 文件路径

    Returns:
        十六进制格式的 SHA-256 哈希值
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


def check_duplicate(checksum: str, project_id: str, db: Any) -> bool:
    """检查文件是否已存在（基于 checksum 精确去重）。

    Args:
        checksum: 文件的 SHA-256 哈希值
        project_id: 项目 ID
        db: 数据库连接/会话

    Returns:
        True 表示已存在（重复），False 表示不重复
    """
    try:
        # 尝试使用 psycopg 连接池
        with db.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE checksum = %s AND project_id = %s",
                (checksum, project_id),
            )
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
    except AttributeError:
        # 尝试 SQLAlchemy Session
        try:
            from sqlalchemy import text
            result = db.execute(
                text("SELECT COUNT(*) FROM documents WHERE checksum = :checksum AND project_id = :project_id"),
                {"checksum": checksum, "project_id": project_id},
            )
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
        except Exception as e:
            logger.error("去重查询失败: %s", e)
            return False
    except Exception as e:
        logger.error("去重查询失败: %s", e)
        return False


def fuzzy_dedup(
    content: str,
    project_id: str,
    milvus_client: Any,
    threshold: float = 0.95,
) -> bool:
    """基于向量相似度的模糊去重。

    将内容向量化后，在 Milvus 中搜索最相似的已有分块，
    如果相似度超过阈值则认为是重复内容。

    Args:
        content: 待检查的文本内容
        project_id: 项目 ID
        milvus_client: Milvus 连接/Collection 对象
        threshold: 相似度阈值，超过此值认为是重复

    Returns:
        True 表示存在相似内容（疑似重复），False 表示不重复
    """
    if not content or len(content.strip()) < 10:
        return False

    try:
        # 获取内容的向量表示
        from backend.app.processors.embedding import EmbeddingService

        embedding_service = EmbeddingService()
        vector = embedding_service.encode_single(content)

        if not vector:
            logger.warning("向量化失败，跳过模糊去重")
            return False

        # 在 Milvus 中搜索相似向量
        from pymilvus import Collection

        collection = milvus_client if not isinstance(milvus_client, type) else Collection("rag_chunks")
        collection.load()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = collection.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=5,
            expr=f'project_id == "{project_id}"',
            output_fields=["content", "document_id"],
        )

        if results and len(results) > 0:
            for hit in results[0]:
                similarity = hit.distance  # COSINE 距离即相似度
                if similarity >= threshold:
                    logger.info(
                        "模糊去重命中: similarity=%.4f >= threshold=%.4f, doc_id=%s",
                        similarity, threshold, hit.entity.get("document_id", ""),
                    )
                    return True

        return False

    except ImportError as e:
        logger.warning("去重依赖未安装: %s", e)
        return False
    except Exception as e:
        logger.error("模糊去重检查失败: %s", e)
        return False

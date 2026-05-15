"""Deduplication utilities: exact dedup (SHA-256) and fuzzy dedup (vector similarity)."""

from __future__ import annotations

import hashlib
import logging
import uuid as _uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _validate_uuid(value: str) -> str:
    """Validate that a value is a properly formatted UUID to prevent filter injection."""
    return str(_uuid.UUID(value))


def compute_file_hash(file_path: str) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


def check_duplicate(checksum: str, project_id: str, db: Any) -> bool:
    """Check whether a file with the given checksum already exists (exact dedup)."""
    try:
        with db.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE checksum = %s AND project_id = %s",
                (checksum, project_id),
            )
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
    except AttributeError:
        try:
            from sqlalchemy import text

            result = db.execute(
                text(
                    "SELECT COUNT(*) FROM documents "
                    "WHERE checksum = :checksum AND project_id = :project_id"
                ),
                {"checksum": checksum, "project_id": project_id},
            )
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
        except Exception as exc:
            logger.error("Dedup query failed: %s", exc)
            return False
    except Exception as exc:
        logger.error("Dedup query failed: %s", exc)
        return False


def fuzzy_dedup(
    content: str,
    project_id: str,
    milvus_client: Any,
    threshold: float = 0.95,
) -> bool:
    """Fuzzy dedup using vector similarity search.

    Vectorizes the content, searches Milvus for the most similar existing
    chunks, and returns True if similarity exceeds *threshold*.
    """
    if not content or len(content.strip()) < 10:
        return False

    # Validate project_id to prevent Milvus filter expression injection
    try:
        safe_project_id = _validate_uuid(project_id)
    except ValueError:
        logger.warning("Invalid project_id passed to fuzzy_dedup: %s", project_id)
        return False

    try:
        import asyncio

        from app.processors.embedding import EmbeddingService

        embedding_service = EmbeddingService()
        vector = asyncio.run(embedding_service.encode_single(content))

        if not vector:
            logger.warning("Vectorization failed, skipping fuzzy dedup")
            return False

        from pymilvus import Collection

        collection = milvus_client if not isinstance(milvus_client, type) else Collection("rag_chunks")
        collection.load()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = collection.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=5,
            expr=f'project_id == "{safe_project_id}"',
            output_fields=["content", "document_id"],
        )

        if results and len(results) > 0:
            for hit in results[0]:
                similarity = hit.distance
                if similarity >= threshold:
                    logger.info(
                        "Fuzzy dedup hit: similarity=%.4f >= threshold=%.4f, doc_id=%s",
                        similarity, threshold, hit.entity.get("document_id", ""),
                    )
                    return True

        return False

    except ImportError as exc:
        logger.warning("Dedup dependency not installed: %s", exc)
        return False
    except Exception as exc:
        logger.error("Fuzzy dedup check failed: %s", exc)
        return False

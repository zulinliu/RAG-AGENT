"""
Milvus Collection initialization script.

Creates the rag_chunks collection with dense vector index for RAG retrieval.
Run this after Milvus is healthy.
"""

import logging
import os
import time

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, MilvusClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))
COLLECTION_NAME = "rag_chunks"
VECTOR_DIM = 1024


def wait_for_milvus(host: str, port: int, timeout: int = 120) -> None:
    """Block until Milvus is reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client = MilvusClient(uri=f"http://{host}:{port}")
            client.list_collections()
            logger.info("Milvus is ready.")
            return
        except Exception:
            logger.info("Waiting for Milvus ...")
            time.sleep(3)
    raise RuntimeError(f"Milvus not reachable at {host}:{port} after {timeout}s")


def create_collection() -> None:
    """Create the rag_chunks collection if it does not exist."""
    client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

    if client.has_collection(COLLECTION_NAME):
        logger.info("Collection '%s' already exists, skipping.", COLLECTION_NAME)
        return

    # ── Schema ────────────────────────────────────────────────────────
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            description="Unique chunk identifier",
        ),
        FieldSchema(
            name="project_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_partition_key=True,
            description="Project identifier for partition pruning",
        ),
        FieldSchema(
            name="document_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="Source document identifier",
        ),
        FieldSchema(
            name="chunk_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="Chunk identifier within document",
        ),
        FieldSchema(
            name="content",
            dtype=DataType.VARCHAR,
            max_length=4096,
            enable_analyzer=True,
            description="Chunk text content (analyzer-enabled for full-text search)",
        ),
        FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=VECTOR_DIM,
            description="Dense embedding vector",
        ),
        FieldSchema(
            name="chunk_type",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Chunk type (e.g. text, table, code)",
        ),
        FieldSchema(
            name="title",
            dtype=DataType.VARCHAR,
            max_length=512,
            description="Chunk title",
        ),
        FieldSchema(
            name="author",
            dtype=DataType.VARCHAR,
            max_length=128,
            description="Document author",
        ),
        FieldSchema(
            name="source_type",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Source type (e.g. git, confluence, local_file)",
        ),
        FieldSchema(
            name="hierarchy",
            dtype=DataType.JSON,
            description="Hierarchical path within the document",
        ),
        FieldSchema(
            name="created_at",
            dtype=DataType.INT64,
            description="Creation timestamp (epoch seconds)",
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="RAG chunk storage with dense vectors",
    )

    collection = Collection(
        name=COLLECTION_NAME,
        schema=schema,
    )

    # ── Dense vector index (HNSW) ─────────────────────────────────────
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {
            "M": 16,
            "efConstruction": 256,
        },
    }
    collection.create_index(
        field_name="vector",
        index_params=index_params,
    )
    logger.info("Created HNSW index on 'vector' field.")

    # ── Load into memory ──────────────────────────────────────────────
    collection.load()
    logger.info("Collection '%s' loaded and ready.", COLLECTION_NAME)


def main() -> None:
    logger.info("Initializing Milvus collection at %s:%s ...", MILVUS_HOST, MILVUS_PORT)
    wait_for_milvus(MILVUS_HOST, MILVUS_PORT)
    create_collection()
    logger.info("Done.")


if __name__ == "__main__":
    main()

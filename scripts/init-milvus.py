#!/usr/bin/env python
"""
Initialize Milvus:
    1. Wait for Milvus to be healthy
    2. Create rag_chunks collection with schema and HNSW index
"""
import os
import sys

# Ensure the config directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "config"))

from milvus.collection import main

if __name__ == "__main__":
    main()

"""Embedding service supporting multiple providers.

Providers:
  - tei:         HuggingFace TEI Docker (primary, recommended)
  - siliconflow: 硅基流动 API (cloud, same bge models)
  - zhipu:       智谱AI Embedding-3 (cloud, proprietary model)
  - openai:      OpenAI-compatible endpoint (relay / NewAPI)
  - custom:      any OpenAI-compatible endpoint
  - local-py:    load model in-process via transformers (dev only)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding vectorization service with multi-provider support."""

    def __init__(
        self,
        provider: str = "tei",
        api_url: str = "",
        api_key: Optional[str] = None,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        timeout: int = 60,
        batch_size: int = 32,
        device: str = "cpu",
    ) -> None:
        self.provider = provider.lower()
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.batch_size = batch_size
        self.device = device
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    async def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into vectors (async)."""
        if not texts:
            return []

        if self.provider == "local-py":
            return self._encode_local(texts)
        return await self._encode_remote(texts)

    async def encode_single(self, text: str) -> list[float]:
        """Encode a single text (async)."""
        result = await self.encode([text])
        return result[0] if result else []

    # ------------------------------------------------------------------
    # Remote mode (all providers except local-py)
    # ------------------------------------------------------------------

    async def _encode_remote(self, texts: list[str]) -> list[list[float]]:
        """Call a remote embedding service via async HTTP.

        Auto-detects response format:
        1. TEI format:    ``[{"index": 0, "embedding": [...]}]``
        2. OpenAI format: ``{"data": [{"embedding": [...]}]}``
        3. Custom format: ``{"vectors": [...]}`` or ``{"embeddings": [...]}``
        """
        all_vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                payload = self._build_request(batch)
                headers = self._build_headers()

                try:
                    resp = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    all_vectors.extend(self._parse_response(data, len(batch)))
                except httpx.HTTPError as exc:
                    logger.error("Embedding service call failed: %s", exc)
                    raise RuntimeError(f"Embedding service call failed: {exc}") from exc

        return all_vectors

    def _build_request(self, batch: list[str]) -> dict[str, Any]:
        """Build the request payload based on provider type."""
        if self.provider == "tei":
            return {"inputs": batch}
        # OpenAI-compatible (siliconflow, zhipu, openai, custom)
        return {"model": self.model_name, "input": batch}

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _parse_response(self, data: Any, expected_count: int) -> list[list[float]]:
        """Parse embedding response handling multiple formats."""
        # TEI format: [{"index": 0, "embedding": [...]}, ...]
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict) and "embedding" in first:
                return [item["embedding"] for item in data]

        # OpenAI format: {"data": [{"embedding": [...]}]}
        openai_data = data.get("data") if isinstance(data, dict) else None
        if isinstance(openai_data, list) and len(openai_data) > 0:
            first = openai_data[0]
            if isinstance(first, dict) and "embedding" in first:
                return [item["embedding"] for item in openai_data]

        # Custom format fallback: {"vectors": [...]} or {"embeddings": [...]}
        if isinstance(data, dict):
            vectors = (
                data.get("vectors")
                or data.get("embeddings")
                or data.get("data", [])
            )
            if isinstance(vectors, list) and len(vectors) > 0:
                return vectors

        raise RuntimeError(
            f"Unexpected embedding response format: {type(data).__name__}"
        )

    # ------------------------------------------------------------------
    # Local mode (in-process transformers)
    # ------------------------------------------------------------------

    def _encode_local(self, texts: list[str]) -> list[list[float]]:
        """Encode using a locally loaded model (dev only)."""
        self._ensure_model_loaded()

        import numpy as np
        import torch

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            with torch.no_grad():
                outputs = self._model(**encoded)

            attention_mask = encoded["attention_mask"]
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(
                token_embeddings.size()
            ).float()
            embedding = torch.sum(
                token_embeddings * input_mask_expanded, 1
            ) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
            vectors = embedding.cpu().numpy().tolist()
            all_vectors.extend(vectors)

        return all_vectors

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            logger.info(
                "Loading local embedding model: %s (device=%s)",
                self.model_name,
                self.device,
            )
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()
            logger.info("Local embedding model loaded successfully")
        except ImportError:
            raise ImportError(
                "Local embedding mode requires transformers and torch: "
                "pip install transformers torch"
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to load embedding model: {exc}") from exc

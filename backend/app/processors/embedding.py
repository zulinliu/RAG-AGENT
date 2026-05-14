"""Embedding service supporting local model and remote HTTP modes."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding vectorization service.

    Supports two modes:
    - remote: calls a remote embedding service via HTTP (default, recommended for production)
    - local: loads BAAI/bge-large-zh-v1.5 locally for inference (dev/test)
    """

    def __init__(
        self,
        mode: str = "remote",
        # Remote mode parameters
        api_url: str = "http://embedding-worker:8100",
        api_key: Optional[str] = None,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        timeout: int = 60,
        # Local mode parameters
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.mode = mode.lower()
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.device = device
        self.batch_size = batch_size
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into vectors.

        Args:
            texts: texts to encode

        Returns:
            List of embedding vectors; dimension depends on the model.
        """
        if not texts:
            return []

        if self.mode == "remote":
            return self._encode_remote(texts)
        elif self.mode == "local":
            return self._encode_local(texts)
        else:
            raise ValueError(f"Unsupported mode: {self.mode}, use 'remote' or 'local'")

    def encode_single(self, text: str) -> list[float]:
        """Encode a single text."""
        result = self.encode([text])
        return result[0] if result else []

    # ------------------------------------------------------------------
    # Remote mode
    # ------------------------------------------------------------------

    def _encode_remote(self, texts: list[str]) -> list[list[float]]:
        """Call a remote embedding service via HTTP.

        Supports two response formats:
        1. OpenAI-compatible: request ``{"model": ..., "input": [...]}``,
           response ``{"data": [{"embedding": [...]}]}``
        2. Custom: request ``{"texts": [...]}``,
           response ``{"vectors": [...]}`` or ``{"embeddings": [...]}``
        """
        import requests

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            # Try OpenAI-compatible format first
            payload: dict[str, Any] = {
                "model": self.model_name,
                "input": batch,
            }

            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                # OpenAI-compatible response: {"data": [{"embedding": [...]}]}
                openai_data = data.get("data")
                if isinstance(openai_data, list) and len(openai_data) > 0:
                    first_item = openai_data[0]
                    if isinstance(first_item, dict) and "embedding" in first_item:
                        all_vectors.extend(
                            [item["embedding"] for item in openai_data]
                        )
                        continue

                # Custom format fallback: {"vectors": [...]} or {"embeddings": [...]}
                vectors = (
                    data.get("vectors")
                    or data.get("embeddings")
                    or data.get("data", [])
                )
                if isinstance(vectors, list) and len(vectors) > 0:
                    all_vectors.extend(vectors)
                else:
                    raise RuntimeError(
                        f"Unexpected embedding response format: {list(data.keys())}"
                    )

            except requests.RequestException as exc:
                logger.error("Remote embedding service call failed: %s", exc)
                raise RuntimeError(f"Embedding service call failed: {exc}") from exc

        return all_vectors

    # ------------------------------------------------------------------
    # Local mode
    # ------------------------------------------------------------------

    def _encode_local(self, texts: list[str]) -> list[list[float]]:
        """Encode using a locally loaded model."""
        self._ensure_model_loaded()

        import numpy as np
        import torch

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            encoded = self._tokenizer(  # type: ignore[misc]
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            with torch.no_grad():
                outputs = self._model(**encoded)  # type: ignore[misc]

            # Use mean-pooling over the [CLS] token output
            attention_mask = encoded["attention_mask"]
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            embedding = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
                input_mask_expanded.sum(1), min=1e-9
            )
            # Normalize
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
            vectors = embedding.cpu().numpy().tolist()
            all_vectors.extend(vectors)

        return all_vectors

    def _ensure_model_loaded(self) -> None:
        """Load the local model lazily on first use."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            logger.info("Loading embedding model: %s (device=%s)", self.model_name, self.device)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.to(self.device)  # type: ignore[union-attr]
            self._model.eval()  # type: ignore[union-attr]
            logger.info("Model loaded successfully")
        except ImportError:
            raise ImportError(
                "Local embedding mode requires transformers and torch: "
                "pip install transformers torch"
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to load embedding model: {exc}") from exc

"""Embedding 服务，支持本地模型和远程 HTTP 两种模式。"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 向量化服务。

    支持两种模式:
    - remote: 通过 HTTP 调用远程 embedding 服务（默认模式，生产推荐）
    - local: 加载 bge-large-zh-v1.5 模型本地推理（开发/测试）
    """

    def __init__(
        self,
        mode: str = "remote",
        # 远程模式参数
        api_url: str = "http://embedding-service:8001/embed",
        api_key: Optional[str] = None,
        timeout: int = 60,
        # 本地模式参数
        model_name: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.mode = mode.lower()
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

    def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本列表编码为向量列表。

        Args:
            texts: 待编码的文本列表

        Returns:
            向量列表，每个向量的维度取决于模型
        """
        if not texts:
            return []

        if self.mode == "remote":
            return self._encode_remote(texts)
        elif self.mode == "local":
            return self._encode_local(texts)
        else:
            raise ValueError(f"不支持的模式: {self.mode}，请使用 'remote' 或 'local'")

    def encode_single(self, text: str) -> List[float]:
        """编码单个文本。"""
        result = self.encode([text])
        return result[0] if result else []

    # ------------------------------------------------------------------
    # 远程模式
    # ------------------------------------------------------------------

    def _encode_remote(self, texts: List[str]) -> List[List[float]]:
        """通过 HTTP 调用远程 embedding 服务。"""
        import requests

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 分批调用
        all_vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i: i + self.batch_size]
            payload = {"texts": batch}

            try:
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                vectors = data.get("vectors") or data.get("embeddings") or data.get("data", [])
                all_vectors.extend(vectors)
            except requests.RequestException as e:
                logger.error("远程 embedding 服务调用失败: %s", e)
                raise RuntimeError(f"Embedding 服务调用失败: {e}") from e

        return all_vectors

    # ------------------------------------------------------------------
    # 本地模式
    # ------------------------------------------------------------------

    def _encode_local(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型编码。"""
        self._ensure_model_loaded()

        import torch
        import numpy as np

        all_vectors: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i: i + self.batch_size]
            encoded = self._tokenizer(  # type: ignore[misc]
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            with torch.no_grad():
                outputs = self._model(**encoded)  # type: ignore[misc]

            # 使用 [CLS] token 的输出作为句子向量
            attention_mask = encoded["attention_mask"]
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            embedding = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
                input_mask_expanded.sum(1), min=1e-9
            )
            # 归一化
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
            vectors = embedding.cpu().numpy().tolist()
            all_vectors.extend(vectors)

        return all_vectors

    def _ensure_model_loaded(self) -> None:
        """确保本地模型已加载。"""
        if self._model is not None:
            return

        try:
            from transformers import AutoTokenizer, AutoModel
            import torch

            logger.info("加载 embedding 模型: %s (device=%s)", self.model_name, self.device)
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.to(self.device)  # type: ignore[union-attr]
            self._model.eval()  # type: ignore[union-attr]
            logger.info("模型加载完成")
        except ImportError:
            raise ImportError(
                "本地 embedding 模式需要安装 transformers 和 torch: "
                "pip install transformers torch"
            )
        except Exception as e:
            raise RuntimeError(f"加载 embedding 模型失败: {e}") from e

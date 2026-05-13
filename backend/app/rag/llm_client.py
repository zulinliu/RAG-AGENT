"""LLM 客户端 — 通过 HTTP 调用 vLLM 服务 (OpenAI 兼容 API)。"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"
DEFAULT_TIMEOUT = 120.0
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 2048
MAX_RETRIES = 3


class LLMClient:
    """通过 HTTP 调用 vLLM 服务的 LLM 客户端。"""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str = "EMPTY",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=30.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Text generation (non-streaming)
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """生成文本（非流式）。

        支持两种调用方式:
          - prompt: 单条提示文本
          - messages: 对话消息列表
        二者至少提供一个。
        """
        if messages is None:
            if prompt is None:
                raise ValueError("prompt and messages cannot both be None")
            messages = [{"role": "user", "content": prompt}]

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                logger.debug(
                    "generate: tokens used prompt=%s, completion=%s",
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )
                return content
            except Exception:
                logger.exception(
                    "generate attempt %d/%d failed", attempt, MAX_RETRIES
                )
                if attempt == MAX_RETRIES:
                    raise

        return ""  # unreachable but satisfies type checker

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def stream_generate(
        self,
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        """流式生成文本。"""
        if messages is None:
            if prompt is None:
                raise ValueError("prompt and messages cannot both be None")
            messages = [{"role": "user", "content": prompt}]

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception:
            logger.exception("stream_generate failed")
            yield "[生成错误，请重试]"

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    async def count_tokens(self, text: str) -> int:
        """调用 vLLM tokenize 端点计算 token 数。"""
        try:
            resp = await self._client.post(
                "/tokenize",
                json={"model": self._model, "text": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("count", len(text))
        except Exception:
            logger.exception("tokenize failed, falling back to estimate")
            return int(len(text) / 1.5)

    # ------------------------------------------------------------------
    # Embedding (convenience)
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """调用 embedding 端点获取文本向量。"""
        try:
            resp = await self._client.post(
                "/embeddings",
                json={"model": self._model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
        except Exception:
            logger.exception("embedding failed")
            raise

"""LLM client -- calls OpenAI-compatible chat completions via HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 2048
MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds, doubles on each retry

# HTTP status codes that are worth retrying
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class LLMClient:
    """LLM client that talks to any OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Qwen2.5-72B-Instruct",
        api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key or "EMPTY"
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
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Return True for transient errors that are worth retrying."""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout)):
            return True
        return False

    async def _retry_request(self, method: str, path: str, payload: dict[str, Any]) -> httpx.Response:
        """Send a request with exponential back-off on transient failures."""
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, json=payload)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc) or attempt == MAX_RETRIES:
                    raise
                delay = _BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Request to %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    path, attempt, MAX_RETRIES, delay, exc,
                )
                await asyncio.sleep(delay)
        # Should be unreachable, but satisfy the type checker.
        raise last_exc  # type: ignore[misc]

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
        """Generate text (non-streaming).

        Accepts either a single *prompt* string or a *messages* list.
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

        resp = await self._retry_request("POST", "/chat/completions", payload)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        logger.debug(
            "generate: tokens used prompt=%s, completion=%s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        return content

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
        """Stream generated text chunks."""
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
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    # Process complete lines from the buffer
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        # Handle lines that may or may not have the "data: " prefix
                        if line.startswith("data: "):
                            data_str = line[6:]
                        elif line.startswith("data:"):
                            data_str = line[5:]
                        else:
                            data_str = line

                        data_str = data_str.strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception:
            logger.exception("stream_generate failed")
            yield "[generation error, please retry]"

    # ------------------------------------------------------------------
    # Token counting (estimation only)
    # ------------------------------------------------------------------

    async def count_tokens(self, text: str) -> int:
        """Estimate token count without calling a model-specific endpoint.

        Uses a simple heuristic: ~1.5 characters per token for Chinese-heavy
        text, which is a reasonable approximation for most modern LLMs.
        """
        return int(len(text) / 1.5)

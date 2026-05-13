from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx

from rag_qa.core.exceptions import LLMException


class LLMClient:
    def __init__(self, api_base: str, api_key: str = "empty", model_name: str = "Qwen2.5-72B-Instruct"):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        )

    async def generate(
        self, messages: list[dict[str, Any]], temperature: float = 0.7, max_tokens: int = 2048
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = self._build_headers()
        url = f"{self.api_base}/chat/completions"
        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            content: str = data["choices"][0]["message"]["content"]
            return content
        except httpx.HTTPStatusError as e:
            raise LLMException(f"LLM API returned status {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise LLMException(f"LLM API request failed: {e}") from e
        except (KeyError, IndexError) as e:
            raise LLMException(f"Unexpected LLM API response format: {e}") from e

    async def generate_stream(
        self, messages: list[dict[str, Any]], temperature: float = 0.7, max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = self._build_headers()
        url = f"{self.api_base}/chat/completions"
        try:
            async with self._client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break
                    import json

                    try:
                        chunk_data: dict[str, Any] = json.loads(data_str)
                        delta: dict[str, Any] = chunk_data["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except httpx.HTTPStatusError as e:
            raise LLMException(f"LLM streaming API returned status {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise LLMException(f"LLM streaming API request failed: {e}") from e

    async def close(self) -> None:
        await self._client.aclose()

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

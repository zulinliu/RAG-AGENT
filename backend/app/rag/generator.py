"""答案生成器 — 基于 RAG 上下文和对话历史生成回答。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的项目知识问答助手。基于提供的项目文档资料，准确回答用户的问题。

【核心规则】
1. 仅基于提供的参考资料回答问题
2. 每个事实声明必须引用来源文档编号，格式为[来源N]
3. 参考资料不足时回答"根据现有项目资料，我没有找到相关信息"
4. 资料矛盾时指出矛盾并分别引用
5. 回答简洁准确
6. 用户问题模糊时先澄清"""


@dataclass
class AnswerResult:
    """生成答案的结果。"""

    content: str
    citations: list[int] = field(default_factory=list)
    confidence_score: float = 0.0
    sources_used: list[str] = field(default_factory=list)


class AnswerGenerator:
    """基于检索上下文的答案生成器。"""

    def __init__(self, default_temperature: float = 0.1, max_tokens: int = 2048) -> None:
        self._temperature = default_temperature
        self._max_tokens = max_tokens

    async def generate_answer(
        self,
        query: str,
        context: str,
        conversation_history: list[dict[str, str]] | None = None,
        llm_client: Any | None = None,
    ) -> AnswerResult:
        """生成答案（非流式）。"""
        if llm_client is None:
            raise ValueError("llm_client is required for generate_answer but was None")
        messages = self._build_messages(query, context, conversation_history)
        try:
            content = await llm_client.generate(
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return AnswerResult(content=content.strip())
        except Exception:
            logger.exception("answer generation failed")
            return AnswerResult(content="抱歉，生成答案时出现错误，请稍后重试。")

    async def stream_answer(
        self,
        query: str,
        context: str,
        conversation_history: list[dict[str, str]] | None = None,
        llm_client: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成答案（SSE 用）。"""
        if llm_client is None:
            raise ValueError("llm_client is required for stream_answer but was None")
        messages = self._build_messages(query, context, conversation_history)
        try:
            async for chunk in llm_client.stream_generate(messages=messages):
                yield chunk
        except Exception:
            logger.exception("stream answer generation failed")
            yield "抱歉，生成答案时出现错误，请稍后重试。"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        query: str,
        context: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        if conversation_history:
            for msg in conversation_history[-10:]:  # 保留最近10轮
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        user_content = f"{context}\n\n用户问题：{query}"
        messages.append({"role": "user", "content": user_content})
        return messages

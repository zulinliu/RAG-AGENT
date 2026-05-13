"""QA 编排服务 — 串联 CRAG 管道、对话管理和反馈。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from app.rag.graph import CRAGPipeline, QueryState
from app.rag.session_manager import SessionManager

logger = logging.getLogger(__name__)


@dataclass
class AskResponse:
    """同步问答响应。"""

    conversation_id: str
    message_id: str
    query: str
    answer: str
    citations: list[int] = field(default_factory=list)
    confidence: float = 0.0
    sources_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class QAService:
    """QA 编排服务，串联 CRAG 管道和对话管理。"""

    def __init__(
        self,
        pipeline: CRAGPipeline,
        session_manager: SessionManager,
    ) -> None:
        self._pipeline = pipeline
        self._session = session_manager

    async def ask(
        self,
        user_id: str,
        project_id: str,
        query: str,
        conversation_id: str | None = None,
    ) -> AskResponse:
        """同步问答。"""
        # 创建或复用对话
        if not conversation_id:
            conversation_id = await self._session.create_conversation(
                user_id, project_id
            )

        # 获取对话历史
        history = await self._session.get_conversation_history_for_llm(conversation_id)

        # 压缩上下文（如需要）
        await self._session.compress_context(conversation_id, None)

        # 记录用户消息
        user_msg_id = await self._session.add_message(
            conversation_id, "user", query
        )

        # 执行 CRAG 管道
        state: QueryState = await self._pipeline.run(
            query=query,
            project_id=project_id,
            conversation_history=history,
        )

        # 记录助手回复
        assistant_msg_id = await self._session.add_message(
            conversation_id,
            "assistant",
            state.answer,
            metadata={
                "citations": state.citations,
                "confidence": state.confidence,
                "rewritten_query": state.rewritten_query,
                "intent": state.intent,
            },
        )

        sources_used = [d.chunk_id for d in state.reranked_docs]

        return AskResponse(
            conversation_id=conversation_id,
            message_id=assistant_msg_id,
            query=query,
            answer=state.answer,
            citations=state.citations,
            confidence=state.confidence,
            sources_used=sources_used,
            metadata={
                "user_message_id": user_msg_id,
                "rewritten_query": state.rewritten_query,
                "intent": state.intent,
            },
        )

    async def stream_ask(
        self,
        user_id: str,
        project_id: str,
        query: str,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式问答，逐步输出。"""
        # 创建或复用对话
        if not conversation_id:
            conversation_id = await self._session.create_conversation(
                user_id, project_id
            )

        # 记录用户消息
        await self._session.add_message(conversation_id, "user", query)

        # 获取对话历史
        history = await self._session.get_conversation_history_for_llm(conversation_id)

        # 流式执行 CRAG 管道
        full_answer = ""
        async for event in self._pipeline.stream(
            query=query,
            project_id=project_id,
            conversation_history=history,
        ):
            yield {
                "type": "pipeline_event",
                "data": event,
                "conversation_id": conversation_id,
            }

            # 从 generate 事件中提取答案文本
            if isinstance(event, dict):
                for node_name, state_update in event.items():
                    if node_name == "generate" and isinstance(state_update, dict):
                        answer = state_update.get("answer", "")
                        if answer:
                            full_answer = answer

        # 记录完整回复
        if full_answer:
            await self._session.add_message(
                conversation_id,
                "assistant",
                full_answer,
            )

    async def submit_feedback(
        self,
        message_id: str,
        feedback: str,
    ) -> None:
        """提交用户反馈。"""
        if feedback not in ("thumbs_up", "thumbs_down"):
            raise ValueError(f"Invalid feedback type: {feedback}")
        await self._session.add_feedback(message_id, feedback)

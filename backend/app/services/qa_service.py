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
        """流式问答，逐 token 输出。"""
        # 创建或复用对话
        if not conversation_id:
            conversation_id = await self._session.create_conversation(
                user_id, project_id
            )

        # 记录用户消息
        await self._session.add_message(conversation_id, "user", query)

        # 获取对话历史
        history = await self._session.get_conversation_history_for_llm(conversation_id)

        # Phase 1: 执行检索管道（route -> understand -> retrieve -> grade -> rerank）
        state = await self._pipeline.run_pre_generate(
            query=query,
            project_id=project_id,
            conversation_history=history,
        )

        # Emit retrieval metadata event
        yield {
            "type": "retrieval_done",
            "data": {
                "retrieved_count": len(state.reranked_docs),
                "rewritten_query": state.rewritten_query,
                "intent": state.intent,
            },
            "conversation_id": conversation_id,
        }

        # Phase 2: Stream token-by-token answer generation
        full_answer = ""
        context = self._pipeline._context_builder.build_context(state.reranked_docs)

        async for token in self._pipeline._answer_generator.stream_answer(
            query=query,
            context=context,
            conversation_history=history,
            llm_client=self._pipeline._llm_client,
        ):
            full_answer += token
            yield {
                "type": "text",
                "data": token,
                "conversation_id": conversation_id,
            }

        # Phase 3: Verify citations and score confidence
        verification = self._pipeline._citation_verifier.verify(
            full_answer, state.reranked_docs
        )
        retrieval_scores = [d.score for d in state.reranked_docs]
        confidence = self._pipeline._confidence_scorer.score(
            retrieval_scores=retrieval_scores,
            citation_coverage=verification.citation_coverage,
            answer_length=len(full_answer),
        )

        # Record assistant message
        await self._session.add_message(
            conversation_id,
            "assistant",
            full_answer,
            metadata={
                "citations": verification.valid_citations,
                "confidence": confidence,
                "rewritten_query": state.rewritten_query,
                "intent": state.intent,
            },
        )

        # Emit final metadata event
        yield {
            "type": "done",
            "data": {
                "citations": verification.valid_citations,
                "confidence": confidence,
                "sources_used": [d.chunk_id for d in state.reranked_docs],
            },
            "conversation_id": conversation_id,
        }

    async def submit_feedback(
        self,
        message_id: str,
        feedback: str,
    ) -> None:
        """提交用户反馈。"""
        if feedback not in ("thumbs_up", "thumbs_down"):
            raise ValueError(f"Invalid feedback type: {feedback}")
        await self._session.add_feedback(message_id, feedback)

    async def list_conversations(
        self,
        user_id: str,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取用户对话列表。"""
        return await self._session.list_conversations(user_id, project_id, limit)

    async def get_conversation_history(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        """获取对话详情。"""
        return await self._session.get_history(conversation_id)

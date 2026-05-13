from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.core.exceptions import NotFoundException
from rag_qa.generator.answer_generator import AnswerGenerator, AnswerResult, StreamChunk
from rag_qa.generator.context_builder import RetrievedChunk
from rag_qa.generator.session_manager import SessionManager
from rag_qa.models.conversation import Conversation, FeedbackType, Message


@runtime_checkable
class HybridRetriever(Protocol):
    async def retrieve(self, query: str, project_id: str | None = None, top_k: int = 10) -> list[RetrievedChunk]: ...


class ChatService:
    def __init__(
        self,
        db_session: AsyncSession,
        retriever: HybridRetriever,
        answer_generator: AnswerGenerator,
        session_manager: SessionManager,
    ):
        self.db_session = db_session
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.session_manager = session_manager

    async def chat(
        self,
        query: str,
        user_id: str,
        project_id: str | None = None,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        conversation = await self._get_or_create_conversation(
            user_id, project_id, conversation_id
        )

        history = await self.session_manager.get_history(conversation.id)
        conversation_history = self._build_conversation_history(history)

        resolved_query = await self._resolve_query(query, history)

        chunks = await self.retriever.retrieve(
            query=resolved_query, project_id=conversation.project_id
        )

        result = await self.answer_generator.generate(
            query=resolved_query,
            chunks=chunks,
            conversation_history=conversation_history,
        )

        await self.session_manager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=query,
        )
        sources_dict: dict[str, Any] = {s.source_id: s.model_dump() for s in result.sources}
        await self.session_manager.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=result.answer,
            sources=sources_dict,
            confidence_score=result.confidence,
        )

        await self.db_session.commit()
        return result

    async def chat_stream(
        self,
        query: str,
        user_id: str,
        project_id: str | None = None,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        conversation = await self._get_or_create_conversation(
            user_id, project_id, conversation_id
        )

        history = await self.session_manager.get_history(conversation.id)
        conversation_history = self._build_conversation_history(history)

        resolved_query = await self._resolve_query(query, history)

        chunks = await self.retriever.retrieve(
            query=resolved_query, project_id=conversation.project_id
        )

        await self.session_manager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=query,
        )

        final_answer = ""
        final_metadata: dict[str, Any] | None = None

        async for chunk in self.answer_generator.generate_stream(
            query=resolved_query,
            chunks=chunks,
            conversation_history=conversation_history,
        ):
            if chunk.type == "content" and chunk.content:
                final_answer += chunk.content
            elif chunk.type == "metadata" and chunk.metadata:
                final_metadata = chunk.metadata
            yield chunk

        sources_dict = final_metadata.get("sources", {}) if final_metadata else {}
        confidence = final_metadata.get("confidence") if final_metadata else None

        await self.session_manager.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=final_answer,
            sources=sources_dict,
            confidence_score=confidence,
        )

        await self.db_session.commit()

    async def add_feedback(
        self,
        message_id: str,
        user_id: str,
        feedback_type: str,
        comment: str | None = None,
    ) -> None:
        stmt = select(Message).where(Message.id == message_id)
        result = await self.db_session.execute(stmt)
        message = result.scalar_one_or_none()

        if message is None:
            raise NotFoundException(f"Message {message_id} not found")

        message.feedback_type = FeedbackType(feedback_type)
        message.feedback_comment = comment
        await self.db_session.commit()

    async def _get_or_create_conversation(
        self,
        user_id: str,
        project_id: str | None,
        conversation_id: str | None,
    ) -> Conversation:
        if conversation_id:
            conversation = await self.session_manager.get_conversation(conversation_id)
            if conversation is None:
                raise NotFoundException(f"Conversation {conversation_id} not found")
            return conversation

        if project_id is None:
            project_id = "default"

        return await self.session_manager.create_conversation(
            user_id=user_id,
            project_id=project_id,
        )

    async def _resolve_query(self, query: str, history: list[Message]) -> str:
        if not history:
            return query

        llm_client = self.answer_generator.llm_client
        return await self.session_manager.resolve_coreference(query, history, llm_client)

    @staticmethod
    def _build_conversation_history(history: list[Message]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for msg in history:
            role = "user" if msg.role.value == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        return messages

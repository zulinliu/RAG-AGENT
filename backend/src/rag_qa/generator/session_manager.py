from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.generator.llm_client import LLMClient
from rag_qa.generator.prompt_templates import PromptTemplate
from rag_qa.models.conversation import Conversation, Message, MessageRole


class SessionManager:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self._prompt_template = PromptTemplate()

    async def create_conversation(
        self, user_id: str, project_id: str, title: str | None = None
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            project_id=project_id,
            title=title or "New Conversation",
        )
        self.db_session.add(conversation)
        await self.db_session.flush()
        await self.db_session.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: dict[str, Any] | None = None,
        confidence_score: float | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            citations=sources,
            confidence_score=confidence_score,
        )
        self.db_session.add(message)
        await self.db_session.flush()
        await self.db_session.refresh(message)
        return message

    async def get_history(self, conversation_id: str, limit: int = 20) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db_session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_coreference(
        self, query: str, history: list[Message], llm_client: LLMClient
    ) -> str:
        if not history:
            return query

        history_text = ""
        for msg in history[-6:]:
            role_label = "用户" if msg.role == MessageRole.USER else "助手"
            history_text += f"{role_label}：{msg.content}\n"

        prompt = (
            "请根据对话历史，将用户最新问题中的指代词"
            "（如\"那个项目\"、\"它\"、\"这个方案\"等）替换为具体的实体名称，"
            "使问题在不依赖上下文的情况下也能被理解。\n\n"
            f"对话历史：\n{history_text}\n"
            f"最新问题：{query}\n\n"
            "请直接输出消解指代后的问题，不要添加任何解释。"
            "如果问题中没有指代词，直接原样输出问题。"
        )

        messages = [
            {"role": "system", "content": "你是一个指代消解助手，负责将含有指代词的问题转换为独立完整的问题。"},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await llm_client.generate(messages, temperature=0.1, max_tokens=512)
            resolved = result.strip()
            return resolved if resolved else query
        except Exception:
            return query

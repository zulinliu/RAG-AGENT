"""多轮对话管理 — 上下文维护、压缩、持久化。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import asyncpg  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_CONTEXT_TOKENS = 8000


class SessionManager:
    """管理对话上下文: 存储、加载、压缩。"""

    def __init__(
        self,
        pool: asyncpg.Pool,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> None:
        self._pool = pool
        self._max_rounds = max_rounds
        self._max_context_tokens = max_context_tokens

    async def create_conversation(
        self,
        user_id: str,
        project_id: str,
    ) -> str:
        """创建新对话，返回 conversation_id。"""
        conversation_id = str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (id, user_id, project_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $4)
                """,
                conversation_id,
                user_id,
                project_id,
                datetime.utcnow(),
            )
        logger.info("created conversation %s for user %s", conversation_id, user_id)
        return conversation_id

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """添加消息到对话，返回 message_id。"""
        message_id = str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(metadata or {}, ensure_ascii=False),
                datetime.utcnow(),
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = $1 WHERE id = $2",
                datetime.utcnow(),
                conversation_id,
            )
        return message_id

    async def get_history(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """获取对话历史消息。"""
        effective_limit = limit or self._max_rounds * 2
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, metadata, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                conversation_id,
                effective_limit,
            )
        return [
            {
                "message_id": str(r["id"]),
                "role": r["role"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def get_conversation_history_for_llm(
        self,
        conversation_id: str,
    ) -> list[dict[str, str]]:
        """获取对话历史用于 LLM 调用（role/content 格式）。"""
        messages = await self.get_history(conversation_id)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]

    async def compress_context(
        self,
        conversation_id: str,
        llm_client: Any,
    ) -> None:
        """当对话历史过长时，压缩早期对话为摘要。"""
        messages = await self.get_history(conversation_id)
        total_chars = sum(len(m["content"]) for m in messages)
        estimated_tokens = int(total_chars / 1.5)  # 中文约 1.5 字符/token

        if estimated_tokens <= self._max_context_tokens:
            return

        # 压缩前半部分对话为摘要
        half = len(messages) // 2
        old_messages = messages[:half]

        summary_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in old_messages
        )
        prompt = (
            "请将以下对话历史压缩为一段简洁的摘要，保留关键信息。\n"
            "仅输出摘要内容，不要任何解释。\n\n"
            f"{summary_text}"
        )
        try:
            summary = await llm_client.generate(prompt, temperature=0.1, max_tokens=512)
        except Exception:
            logger.exception("context compression failed")
            return

        # 删除旧消息，插入摘要
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for m in old_messages:
                    await conn.execute(
                        "DELETE FROM messages WHERE id = $1", m["message_id"]
                    )
                await conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, role, content, metadata, created_at)
                    VALUES ($1, $2, 'system', $3, $4, $5)
                    """,
                    str(uuid.uuid4()),
                    conversation_id,
                    f"[对话摘要] {summary.strip()}",
                    json.dumps({"type": "summary"}, ensure_ascii=False),
                    datetime.utcnow(),
                )
        logger.info("compressed conversation %s: %d -> summary", conversation_id, len(old_messages))

    async def list_conversations(
        self,
        user_id: str,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取用户的对话列表。"""
        async with self._pool.acquire() as conn:
            if project_id:
                rows = await conn.fetch(
                    """
                    SELECT id, project_id, created_at, updated_at
                    FROM conversations
                    WHERE user_id = $1 AND project_id = $2
                    ORDER BY updated_at DESC
                    LIMIT $3
                    """,
                    user_id,
                    project_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, project_id, created_at, updated_at
                    FROM conversations
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
        return [
            {
                "conversation_id": str(r["id"]),
                "project_id": r["project_id"],
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]

    async def add_feedback(
        self,
        message_id: str,
        feedback: str,
    ) -> None:
        """记录用户对某条消息的反馈 (thumbs_up / thumbs_down)。"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE messages
                SET metadata = COALESCE(metadata, '{}')::jsonb || $1::jsonb
                WHERE id = $2
                """,
                json.dumps({"feedback": feedback}),
                message_id,
            )
        logger.info("feedback '%s' recorded for message %s", feedback, message_id)

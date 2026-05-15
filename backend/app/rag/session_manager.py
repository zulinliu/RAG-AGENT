"""多轮对话管理 — 上下文维护、压缩、持久化。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
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

    async def close(self) -> None:
        """Close the underlying connection pool."""
        if self._pool is not None:
            await self._pool.close()

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
                datetime.now(timezone.utc),
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
        """添加消息到对话，返回 message_id。

        Maps to the ORM Message model columns:
          - sources -> sources JSONB column
          - feedback -> feedback column
          - confidence_score -> confidence_score column
          - metadata -> metadata JSONB column
        """
        message_id = str(uuid.uuid4())

        # Work on a copy to avoid mutating the caller's dict
        meta = dict(metadata) if metadata else {}

        # Extract known ORM fields from metadata
        sources = None
        feedback = "none"
        confidence_score = None
        remaining_meta = {}

        if meta:
            sources = meta.pop("sources", None) or meta.pop("citations", None)
            confidence_score = meta.pop("confidence", None) or meta.pop("confidence_score", None)
            fb = meta.pop("feedback", None)
            if fb:
                feedback = fb
            remaining_meta = {k: v for k, v in meta.items() if v is not None}

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, sources, feedback, confidence_score, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(sources, ensure_ascii=False) if sources else None,
                feedback,
                confidence_score,
                json.dumps(remaining_meta, ensure_ascii=False) if remaining_meta else None,
                datetime.now(timezone.utc),
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = $1 WHERE id = $2",
                datetime.now(timezone.utc),
                conversation_id,
            )
        return message_id

    async def set_conversation_title(self, conversation_id: str, title: str) -> None:
        """Set a compact conversation title."""
        compact = title.strip().replace("\n", " ")[:80] or "新对话"
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET title = $1, updated_at = $2 WHERE id = $3",
                compact,
                datetime.now(timezone.utc),
                conversation_id,
            )

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
                SELECT id, role, content, sources, feedback, confidence_score, metadata, created_at
                FROM (
                    SELECT id, role, content, sources, feedback, confidence_score, metadata, created_at
                    FROM messages
                    WHERE conversation_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                ) sub
                ORDER BY created_at ASC
                """,
                conversation_id,
                effective_limit,
            )
        return [
            {
                "id": str(r["id"]),
                "message_id": str(r["id"]),
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r["sources"]) if r["sources"] else None,
                "feedback": r["feedback"] or "none",
                "confidence_score": r["confidence_score"],
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
        estimated_tokens = int(total_chars / 1.5)  # 中文约 1.5 字符/token（与 context_builder 一致）

        if estimated_tokens <= self._max_context_tokens:
            return

        # 压缩前半部分对话为摘要
        half = len(messages) // 2
        old_messages = messages[:half]

        summary_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in old_messages
        )
        prompt = (
            "请将以下对话历史压缩为简洁的摘要，保留关键事实、决策和上下文信息。\n"
            "只输出摘要文本，不要输出其他内容。\n\n"
            "<conversation_history>\n" + summary_text + "\n</conversation_history>"
        )
        try:
            summary = await llm_client.generate(prompt, temperature=0.1, max_tokens=512)
        except Exception:
            logger.exception("context compression failed")
            return

        # 批量删除旧消息，插入摘要
        old_ids = [m["message_id"] for m in old_messages]
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM messages WHERE id = ANY($1::uuid[])",
                    old_ids,
                )
                await conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, role, content, feedback, metadata, created_at)
                    VALUES ($1, $2, 'system', $3, 'none', $4, $5)
                    """,
                    str(uuid.uuid4()),
                    conversation_id,
                    f"[对话摘要] {summary.strip()}",
                    json.dumps({"type": "summary"}, ensure_ascii=False),
                    datetime.now(timezone.utc),
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
                    SELECT id, project_id, title, created_at, updated_at
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
                    SELECT id, project_id, title, created_at, updated_at
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
                "id": str(r["id"]),
                "conversation_id": str(r["id"]),
                "title": r["title"] or "新对话",
                "project_id": r["project_id"],
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """获取对话基本信息（含 user_id）。"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, project_id, title, created_at, updated_at FROM conversations WHERE id = $1",
                conversation_id,
            )
        if row is None:
            return None
        return {
            "conversation_id": str(row["id"]),
            "id": str(row["id"]),
            "title": row["title"] or "新对话",
            "user_id": str(row["user_id"]),
            "project_id": row["project_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    async def get_message_owner(self, message_id: str) -> str | None:
        """获取消息所属对话的 user_id。"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT c.user_id
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.id = $1
                """,
                message_id,
            )
        return str(row["user_id"]) if row else None

    async def delete_conversation(self, conversation_id: str) -> None:
        """删除对话及其所有消息。"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM conversations WHERE id = $1",
                conversation_id,
            )
        logger.info("deleted conversation %s", conversation_id)

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
                SET feedback = $1,
                    metadata = COALESCE(metadata, '{}')::jsonb || $2::jsonb
                WHERE id = $3
                """,
                feedback,
                json.dumps({"feedback": feedback}),
                message_id,
            )
        logger.info("feedback '%s' recorded for message %s", feedback, message_id)

    async def create_feedback_bad_case(self, message_id: str, user_id: str) -> None:
        """Create one open BadCase for a thumbs-down feedback event."""
        bad_case_id = str(uuid.uuid4())
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bad_cases (
                        id, project_id, message_id, created_by, category,
                        description, expected_answer, status, created_at, updated_at
                    )
                    SELECT $1, c.project_id, m.id, $2, 'feedback',
                           '用户点踩该回答', NULL, 'open', $4, $4
                    FROM messages m
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE m.id = $3
                      AND NOT EXISTS (
                          SELECT 1
                          FROM bad_cases b
                          WHERE b.message_id = m.id
                            AND b.category = 'feedback'
                            AND b.status = 'open'
                      )
                    """,
                    bad_case_id,
                    user_id,
                    message_id,
                    datetime.now(timezone.utc),
                )
        except Exception:
            logger.debug("failed to create feedback bad case", exc_info=True)

    async def resolve_feedback_bad_case(self, message_id: str) -> None:
        """Resolve open feedback BadCases when the user marks the answer useful."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bad_cases
                    SET status = 'resolved', resolved_at = $2, updated_at = $2
                    WHERE message_id = $1
                      AND category = 'feedback'
                      AND status = 'open'
                    """,
                    message_id,
                    datetime.now(timezone.utc),
                )
        except Exception:
            logger.debug("failed to resolve feedback bad case", exc_info=True)

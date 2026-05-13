from __future__ import annotations

import hashlib
import hmac
from typing import Any

from rag_qa.generator.answer_generator import SourceRef


class DingTalkBotHandler:
    def __init__(self, chat_service: Any, app_secret: str):
        self._chat_service = chat_service
        self._app_secret = app_secret

    async def handle_message(self, request_body: dict[str, Any]) -> dict[str, Any]:
        headers = request_body.get("headers", {})
        timestamp = headers.get("timestamp", "")
        sign = headers.get("sign", "")

        if not self.verify_signature(timestamp, sign):
            return {"msgtype": "text", "text": {"content": "签名验证失败"}}

        msg = request_body.get("msg", {})
        user_msg = msg.get("content", "").strip()
        user_id = msg.get("senderStaffId") or msg.get("senderId", "unknown")
        conversation_id = msg.get("conversationId")

        if not user_msg:
            return {"msgtype": "text", "text": {"content": "消息内容为空"}}

        try:
            result = await self._chat_service.chat(
                query=user_msg,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return self.format_reply(result.answer, result.sources)
        except Exception as e:
            return {"msgtype": "text", "text": {"content": f"处理消息失败: {e}"}}

    def verify_signature(self, timestamp: str, sign: str) -> bool:
        if not timestamp or not sign:
            return False

        string_to_sign = f"{timestamp}\n{self._app_secret}"
        computed_sign = hmac.new(
            self._app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_sign, sign)

    def format_reply(self, answer: str, sources: list[Any]) -> dict[str, Any]:
        md_parts = [f"### 回答\n\n{answer}"]

        if sources:
            source_lines = []
            for s in sources:
                if isinstance(s, SourceRef):
                    source_lines.append(f"- [{s.source_id}] {s.title}")
                elif isinstance(s, dict):
                    source_lines.append(f"- [{s.get('source_id', '')}] {s.get('title', '')}")
            if source_lines:
                md_parts.append("### 参考来源\n\n" + "\n".join(source_lines))

        markdown_text = "\n\n".join(md_parts)

        return {
            "msgtype": "markdown",
            "markdown": {
                "title": "RAG-QA 回答",
                "text": markdown_text,
            },
        }

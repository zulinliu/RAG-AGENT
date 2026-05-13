from __future__ import annotations

import json
import logging
from enum import StrEnum

logger = logging.getLogger(__name__)

_INTENT_PROMPT = """你是一个查询意图分类器。请判断以下用户查询的意图类型，只返回意图类别名称。

意图类别：
- FACT_QUERY: 事实查询，询问具体的事实、数据、定义等
- SCHEME_QUERY: 方案查询，询问设计方案、技术选型、架构等
- COMPARISON_QUERY: 对比查询，比较两个或多个事物的差异
- PROCESS_QUERY: 流程查询，询问步骤、流程、方法等

用户查询：{query}

请只返回意图类别名称（FACT_QUERY/SCHEME_QUERY/COMPARISON_QUERY/PROCESS_QUERY）："""

_REWRITE_PROMPT = """你是一个查询改写专家。请将用户的口语化、模糊的问题改写为更清晰、更适合检索的形式。
{context}
原始查询：{query}

请直接输出改写后的查询，不要解释："""

_HYDE_PROMPT = (
    "请针对以下问题，写一段假设性的答案。"
    "这段答案不需要完全正确，但应该包含与问题相关的关键词和概念，"
    "用于辅助检索相关文档。\n\n"
    "问题：{query}\n\n"
    "假设性答案："
)

_EXPAND_PROMPT = """你是一个查询分解专家。请将以下复杂问题分解为2-4个简单的子查询，每个子查询关注一个方面。
返回JSON格式的列表，例如：["子查询1", "子查询2", "子查询3"]

原始查询：{query}

请直接返回JSON列表："""


class QueryIntent(StrEnum):
    FACT_QUERY = "FACT_QUERY"
    SCHEME_QUERY = "SCHEME_QUERY"
    COMPARISON_QUERY = "COMPARISON_QUERY"
    PROCESS_QUERY = "PROCESS_QUERY"


class QueryOptimizer:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    async def _chat(self, prompt: str) -> str:
        resp = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )
        return resp.strip()

    async def identify_intent(self, query: str) -> QueryIntent:
        prompt = _INTENT_PROMPT.format(query=query)
        result = await self._chat(prompt)
        for intent in QueryIntent:
            if intent.value in result:
                return intent
        return QueryIntent.FACT_QUERY

    async def rewrite_query(self, query: str, context: str = "") -> str:
        ctx = f"上下文信息：{context}\n" if context else ""
        prompt = _REWRITE_PROMPT.format(query=query, context=ctx)
        return await self._chat(prompt)

    async def generate_hyde(self, query: str) -> str:
        prompt = _HYDE_PROMPT.format(query=query)
        return await self._chat(prompt)

    async def expand_query(self, query: str) -> list[str]:
        prompt = _EXPAND_PROMPT.format(query=query)
        result = await self._chat(prompt)
        try:
            sub_queries = json.loads(result)
            if isinstance(sub_queries, list):
                return [str(q) for q in sub_queries]
        except json.JSONDecodeError:
            pass
        return [query]

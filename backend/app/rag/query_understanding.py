"""查询理解模块 — 改写、关键词提取、意图分类、项目范围检测。"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

import jieba  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    FACT = "fact"
    PLAN = "plan"
    COMPARISON = "comparison"
    PROCESS = "process"
    UNKNOWN = "unknown"


class QueryUnderstanding:
    """查询理解: 改写、关键词提取、意图分类、项目范围检测。"""

    # ------------------------------------------------------------------
    # Query rewriting
    # ------------------------------------------------------------------

    @staticmethod
    async def rewrite_query(query: str, llm_client: Any) -> str:
        """利用 LLM 改写用户查询，使其更利于检索。"""
        prompt = (
            "请将以下用户查询改写为一个更适合语义检索的查询语句。\n"
            "要求:\n"
            "1. 保留原始意图\n"
            "2. 补充隐含的上下文\n"
            "3. 使用更明确的表述\n"
            "4. 仅输出改写后的查询，不要任何解释\n\n"
            f"原始查询: {query}"
        )
        try:
            rewritten = await llm_client.generate(prompt, temperature=0.1, max_tokens=256)
            rewritten = rewritten.strip()
            logger.info("query rewritten: '%s' -> '%s'", query, rewritten)
            return rewritten
        except Exception:
            logger.exception("query rewrite failed, using original")
            return query

    # ------------------------------------------------------------------
    # Keyword extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        """使用 jieba 分词提取关键词。"""
        import jieba.analyse  # type: ignore[import-untyped]

        keywords = jieba.analyse.extract_tags(query, topK=10, withWeight=False)
        logger.info("extracted keywords: %s", keywords)
        return list(keywords)

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    @staticmethod
    async def classify_intent(query: str, llm_client: Any) -> Intent:
        """利用 LLM 判断查询意图。"""
        prompt = (
            "请判断以下用户查询的意图类别，只输出类别名称，不要任何解释。\n"
            "类别选项:\n"
            "- fact: 查询具体事实或数据\n"
            "- plan: 查询计划、方案或策略\n"
            "- comparison: 比较两个或多个事物\n"
            "- process: 查询流程、步骤或方法\n"
            "- unknown: 无法判断\n\n"
            f"查询: {query}"
        )
        try:
            raw = await llm_client.generate(prompt, temperature=0.0, max_tokens=32)
            raw = raw.strip().lower()
            for intent in Intent:
                if intent.value in raw:
                    logger.info("classified intent: %s -> %s", query, intent.value)
                    return intent
            return Intent.UNKNOWN
        except Exception:
            logger.exception("intent classification failed")
            return Intent.UNKNOWN

    # ------------------------------------------------------------------
    # Project scope detection
    # ------------------------------------------------------------------

    @staticmethod
    async def detect_project_scope(
        query: str,
        user_projects: list[dict[str, Any]],
        llm_client: Any,
    ) -> str | None:
        """检测查询是否涉及特定项目，返回 project_id 或 None。"""
        if not user_projects:
            return None

        project_descriptions = "\n".join(
            f"- 项目ID: {p['project_id']}, 名称: {p['name']}, 描述: {p.get('description', '')}"
            for p in user_projects
        )
        prompt = (
            "根据以下用户查询和用户可访问的项目列表，判断查询涉及哪个项目。\n"
            "仅输出项目ID，如果没有匹配的项目则输出 NONE。\n\n"
            f"用户查询: {query}\n\n"
            f"项目列表:\n{project_descriptions}"
        )
        try:
            raw = await llm_client.generate(prompt, temperature=0.0, max_tokens=64)
            raw = raw.strip()
            if raw.upper() == "NONE":
                return None
            for p in user_projects:
                if p["project_id"] == raw:
                    logger.info("detected project scope: %s", raw)
                    return raw
            return None
        except Exception:
            logger.exception("project scope detection failed")
            return None

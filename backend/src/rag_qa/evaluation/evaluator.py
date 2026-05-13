from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from rag_qa.generator.context_builder import RetrievedChunk

logger = logging.getLogger(__name__)


class TestCase(BaseModel):
    question: str
    expected_answer: str | None = None
    project_id: str | None = None


class CaseResult(BaseModel):
    question: str
    answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    sources: list[str]


class EvalResult(BaseModel):
    total_cases: int
    avg_faithfulness: float
    avg_answer_relevancy: float
    avg_context_precision: float
    avg_context_recall: float
    case_results: list[CaseResult]


@runtime_checkable
class LLMProtocol(Protocol):
    async def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str: ...


@runtime_checkable
class EmbeddingProtocol(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class RetrieverProtocol(Protocol):
    async def retrieve(self, query: str, project_id: str | None = None, top_k: int = 10) -> list[RetrievedChunk]: ...


@runtime_checkable
class GeneratorProtocol(Protocol):
    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> Any: ...


class RAGEvaluator:
    def __init__(self, llm_client: LLMProtocol, embedding_client: EmbeddingProtocol | None = None):
        self._llm_client = llm_client
        self._embedding_client = embedding_client

    async def evaluate(
        self,
        test_cases: list[TestCase],
        retriever: RetrieverProtocol,
        generator: GeneratorProtocol,
    ) -> EvalResult:
        case_results: list[CaseResult] = []

        for case in test_cases:
            chunks = await retriever.retrieve(
                query=case.question, project_id=case.project_id, top_k=10
            )

            result = await generator.generate(
                query=case.question, chunks=chunks
            )

            answer = result.answer
            contexts = [c.content for c in chunks]

            faithfulness = await self.evaluate_faithfulness(answer, contexts)
            answer_relevancy = await self.evaluate_answer_relevancy(case.question, answer)
            context_precision = self._compute_context_precision(chunks, case.expected_answer)
            context_recall = self._compute_context_recall(chunks, case.expected_answer)

            sources = list({c.chunk_id for c in chunks})

            case_results.append(
                CaseResult(
                    question=case.question,
                    answer=answer,
                    faithfulness=faithfulness,
                    answer_relevancy=answer_relevancy,
                    context_precision=context_precision,
                    context_recall=context_recall,
                    sources=sources,
                )
            )

        total = len(case_results)
        avg_faith = sum(c.faithfulness for c in case_results) / total if total else 0.0
        avg_rel = sum(c.answer_relevancy for c in case_results) / total if total else 0.0
        avg_cp = sum(c.context_precision for c in case_results) / total if total else 0.0
        avg_cr = sum(c.context_recall for c in case_results) / total if total else 0.0

        return EvalResult(
            total_cases=total,
            avg_faithfulness=round(avg_faith, 4),
            avg_answer_relevancy=round(avg_rel, 4),
            avg_context_precision=round(avg_cp, 4),
            avg_context_recall=round(avg_cr, 4),
            case_results=case_results,
        )

    async def evaluate_faithfulness(self, answer: str, contexts: list[str]) -> float:
        if not answer or not contexts:
            return 0.0

        claims = await self._extract_claims(answer)
        if not claims:
            return 0.0

        supported = 0
        for claim in claims:
            is_supported = await self._check_claim_support(claim, contexts)
            if is_supported:
                supported += 1

        return supported / len(claims)

    async def evaluate_answer_relevancy(self, question: str, answer: str) -> float:
        if not question or not answer:
            return 0.0

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是一个评估专家。请评估答案与问题的相关程度，"
                    "只返回0到1之间的数字，1表示完全相关，0表示完全无关。"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{question}\n\n答案：{answer}\n\n请返回0到1之间的相关性分数，只返回数字。",
            },
        ]

        try:
            response = await self._llm_client.generate(messages, temperature=0.0)
            score = float(response.strip())
            return max(0.0, min(1.0, score))
        except (ValueError, Exception) as e:
            logger.warning("Answer relevancy evaluation failed: %s", e)
            return 0.0

    async def _extract_claims(self, answer: str) -> list[str]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "请从给定答案中提取所有事实性声明。每行一个声明，不要编号，不要额外解释。",
            },
            {
                "role": "user",
                "content": f"答案：{answer}",
            },
        ]

        try:
            response = await self._llm_client.generate(messages, temperature=0.0)
            claims = [line.strip() for line in response.strip().split("\n") if line.strip()]
            return claims
        except Exception as e:
            logger.warning("Claim extraction failed: %s", e)
            return [answer]

    async def _check_claim_support(self, claim: str, contexts: list[str]) -> bool:
        context_text = "\n---\n".join(contexts)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "判断以下声明是否可以从给定的上下文中推导出来。只回答\u201c是\u201d或\u201c否\u201d。",
            },
            {
                "role": "user",
                "content": f"上下文：\n{context_text}\n\n声明：{claim}\n\n该声明是否可以从上下文推导？",
            },
        ]

        try:
            response = await self._llm_client.generate(messages, temperature=0.0)
            return "是" in response.strip()
        except Exception as e:
            logger.warning("Claim support check failed: %s", e)
            return False

    def _compute_context_precision(self, chunks: list[RetrievedChunk], expected_answer: str | None) -> float:
        if not chunks or not expected_answer:
            return 0.0

        relevant_count = 0
        precision_sum = 0.0

        for rank, chunk in enumerate(chunks, start=1):
            keyword_matches = sum(
                1 for kw in expected_answer.split() if kw in chunk.content and len(kw) > 1
            )
            is_relevant = keyword_matches > 0

            if is_relevant:
                relevant_count += 1
                precision_sum += relevant_count / rank

        if relevant_count == 0:
            return 0.0

        return precision_sum / relevant_count

    def _compute_context_recall(self, chunks: list[RetrievedChunk], expected_answer: str | None) -> float:
        if not chunks or not expected_answer:
            return 0.0

        keywords = [kw for kw in expected_answer.split() if len(kw) > 1]
        if not keywords:
            return 0.0

        covered = 0
        for kw in keywords:
            for chunk in chunks:
                if kw in chunk.content:
                    covered += 1
                    break

        return covered / len(keywords)

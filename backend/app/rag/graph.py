"""LangGraph CRAG 管道 — 带自校正循环的检索增强生成工作流。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from langgraph.graph import END, START, StateGraph

from app.rag.citation_verifier import CitationVerifier
from app.rag.confidence_scorer import ConfidenceScorer
from app.rag.context_builder import ContextBuilder
from app.rag.generator import AnswerGenerator, AnswerResult
from app.rag.query_understanding import QueryUnderstanding
from app.rag.reranker import CrossEncoderReranker
from app.rag.retriever import HybridRetriever, SearchResult
from app.rag.rrf import rrf_fusion

logger = logging.getLogger(__name__)

MAX_REWRITE_RETRIES = 2


@dataclass
class QueryState:
    """CRAG 工作流状态。"""

    query: str = ""
    project_id: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    rewritten_query: str = ""
    query_embedding: list[float] = field(default_factory=list)
    retrieved_docs: list[SearchResult] = field(default_factory=list)
    graded_docs: list[SearchResult] = field(default_factory=list)
    reranked_docs: list[SearchResult] = field(default_factory=list)
    context: str = ""
    answer: str = ""
    citations: list[int] = field(default_factory=list)
    confidence: float = 0.0
    retrieval_needed: bool = True
    rewrite_count: int = 0
    intent: str = ""
    # External dependencies injected at runtime
    llm_client: Any = None
    retriever: HybridRetriever | None = None
    reranker: CrossEncoderReranker | None = None
    embedding_fn: Any = None


class CRAGPipeline:
    """基于 LangGraph 的 CRAG (Corrective RAG) 管道。"""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
        llm_client: Any,
        embedding_fn: Any,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._llm_client = llm_client
        self._embedding_fn = embedding_fn
        self._query_understanding = QueryUnderstanding()
        self._context_builder = ContextBuilder()
        self._answer_generator = AnswerGenerator()
        self._citation_verifier = CitationVerifier()
        self._confidence_scorer = ConfidenceScorer()
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(QueryState)

        # Add nodes
        graph.add_node("route_query", self._route_query)
        graph.add_node("understand_query", self._understand_query)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("grade_documents", self._grade_documents)
        graph.add_node("rewrite_query", self._rewrite_query_node)
        graph.add_node("rerank", self._rerank)
        graph.add_node("generate", self._generate)
        graph.add_node("verify", self._verify)

        # Edges
        graph.add_edge(START, "route_query")
        graph.add_conditional_edges(
            "route_query",
            self._should_retrieve,
            {
                True: "understand_query",
                False: END,
            },
        )
        graph.add_edge("understand_query", "retrieve")
        graph.add_edge("retrieve", "grade_documents")
        graph.add_conditional_edges(
            "grade_documents",
            self._has_relevant_docs,
            {
                True: "rerank",
                False: "rewrite_query",
            },
        )
        graph.add_edge("rewrite_query", "retrieve")
        graph.add_edge("rerank", "generate")
        graph.add_edge("generate", "verify")
        graph.add_edge("verify", END)

        return graph.compile()

    # ------------------------------------------------------------------
    # Node: route_query — 决定是否需要检索
    # ------------------------------------------------------------------

    async def _route_query(self, state: QueryState) -> dict:
        """LLM 判断是否需要检索外部文档。"""
        prompt = (
            "判断以下用户查询是否需要检索项目文档来回答。\n"
            "如果查询是问候、闲聊或无需外部知识即可回答，输出 NO。\n"
            "如果查询涉及项目事实、数据、流程等，输出 YES。\n"
            "只输出 YES 或 NO。\n\n"
            f"查询: {state.query}"
        )
        try:
            result = await self._llm_client.generate(prompt, temperature=0.0, max_tokens=8)
            needed = "YES" in result.upper()
            logger.info("route_query: '%s' -> retrieval_needed=%s", state.query, needed)
            return {"retrieval_needed": needed}
        except Exception:
            logger.exception("route_query failed, defaulting to retrieval")
            return {"retrieval_needed": True}

    @staticmethod
    def _should_retrieve(state: QueryState) -> bool:
        return state.retrieval_needed

    # ------------------------------------------------------------------
    # Node: understand_query — 查询理解和改写
    # ------------------------------------------------------------------

    async def _understand_query(self, state: QueryState) -> dict:
        """查询理解和改写。"""
        rewritten_task = asyncio.ensure_future(
            self._query_understanding.rewrite_query(state.query, self._llm_client)
        )
        intent_task = asyncio.ensure_future(
            self._query_understanding.classify_intent(state.query, self._llm_client)
        )
        rewritten, intent = await asyncio.gather(rewritten_task, intent_task)
        return {
            "rewritten_query": rewritten,
            "intent": intent.value if hasattr(intent, "value") else str(intent),
        }

    # ------------------------------------------------------------------
    # Node: retrieve — 混合检索
    # ------------------------------------------------------------------

    async def _retrieve(self, state: QueryState) -> dict:
        """执行混合检索 + RRF 融合。"""
        query_text = state.rewritten_query or state.query
        project_id = state.project_id

        # Generate embedding
        try:
            embedding = await self._embedding_fn(query_text)
        except Exception:
            logger.exception("embedding generation failed")
            return {"retrieved_docs": []}

        # Hybrid search
        multi_results = await self._retriever.hybrid_search(
            query_text=query_text,
            query_embedding=embedding,
            project_id=project_id,
        )

        # RRF fusion
        fused = rrf_fusion(multi_results)
        logger.info("retrieve: %d fused results for '%s'", len(fused), query_text)
        return {"retrieved_docs": fused}

    # ------------------------------------------------------------------
    # Node: grade_documents — 文档相关性评分
    # ------------------------------------------------------------------

    async def _grade_documents(self, state: QueryState) -> dict:
        """LLM 二元判断每篇文档的相关性（并发评分）。"""
        if not state.retrieved_docs:
            return {"graded_docs": []}

        query_text = state.rewritten_query or state.query
        semaphore = asyncio.Semaphore(10)

        async def _grade_single(doc: SearchResult) -> SearchResult | None:
            prompt = (
                "判断以下文档片段是否与用户查询相关。\n"
                "只输出 RELEVANT 或 IRRELEVANT。\n\n"
                f"用户查询: {query_text}\n\n"
                f"文档片段: {doc.content[:500]}"
            )
            async with semaphore:
                try:
                    result = await self._llm_client.generate(
                        prompt, temperature=0.0, max_tokens=8
                    )
                    if "RELEVANT" in result.upper():
                        return doc
                except Exception:
                    logger.exception("grading doc %s failed", doc.chunk_id)
            return None

        results = await asyncio.gather(
            *[_grade_single(doc) for doc in state.retrieved_docs]
        )
        graded = [r for r in results if r is not None]

        logger.info(
            "grade_documents: %d/%d docs graded relevant",
            len(graded),
            len(state.retrieved_docs),
        )
        return {"graded_docs": graded}

    @staticmethod
    def _has_relevant_docs(state: QueryState) -> bool:
        has_docs = len(state.graded_docs) > 0
        if not has_docs and state.rewrite_count < MAX_REWRITE_RETRIES:
            return False  # -> rewrite_query
        return True  # -> rerank (even with 0 docs, proceed)

    # ------------------------------------------------------------------
    # Node: rewrite_query — 改写查询重试
    # ------------------------------------------------------------------

    async def _rewrite_query_node(self, state: QueryState) -> dict:
        """当文档不足时改写查询重试。"""
        new_rewrite_count = state.rewrite_count + 1
        if new_rewrite_count > MAX_REWRITE_RETRIES:
            logger.warning("max rewrite retries reached, proceeding with empty docs")
            return {"rewrite_count": new_rewrite_count}

        prompt = (
            "之前的检索没有找到相关文档。请改写以下查询使其更适合检索。\n"
            "要求:\n"
            "1. 使用同义词\n"
            "2. 拆分为更具体的子问题\n"
            "3. 仅输出改写后的查询\n\n"
            f"原始查询: {state.query}\n"
            f"当前改写: {state.rewritten_query}"
        )
        try:
            rewritten = await self._llm_client.generate(
                prompt, temperature=0.3, max_tokens=256
            )
            return {
                "rewritten_query": rewritten.strip(),
                "rewrite_count": new_rewrite_count,
            }
        except Exception:
            logger.exception("rewrite_query failed")
            return {"rewrite_count": new_rewrite_count}

    # ------------------------------------------------------------------
    # Node: rerank — Cross-Encoder 重排序
    # ------------------------------------------------------------------

    async def _rerank(self, state: QueryState) -> dict:
        """Cross-Encoder 重排序。"""
        docs = state.graded_docs
        if not docs:
            return {"reranked_docs": []}

        query_text = state.rewritten_query or state.query
        reranked = await self._reranker.rerank(query_text, docs)
        return {"reranked_docs": reranked}

    # ------------------------------------------------------------------
    # Node: generate — 答案生成
    # ------------------------------------------------------------------

    async def _generate(self, state: QueryState) -> dict:
        """生成答案。"""
        context = self._context_builder.build_context(state.reranked_docs)
        answer_result = await self._answer_generator.generate_answer(
            query=state.query,
            context=context,
            conversation_history=state.conversation_history,
            llm_client=self._llm_client,
        )
        return {
            "context": context,
            "answer": answer_result.content,
        }

    # ------------------------------------------------------------------
    # Node: verify — 引用验证和置信度评分
    # ------------------------------------------------------------------

    def _verify(self, state: QueryState) -> dict:
        """引用验证 + 置信度评分。"""
        docs = state.reranked_docs

        verification = self._citation_verifier.verify(state.answer, docs)

        retrieval_scores = [d.score for d in docs]
        confidence = self._confidence_scorer.score(
            retrieval_scores=retrieval_scores,
            citation_coverage=verification.citation_coverage,
            answer_length=len(state.answer),
        )

        return {
            "citations": verification.valid_citations,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Public API: sync execution
    # ------------------------------------------------------------------

    async def run(
        self,
        query: str,
        project_id: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> QueryState:
        """同步执行 CRAG 管道。"""
        initial_state = {
            "query": query,
            "project_id": project_id,
            "conversation_history": conversation_history or [],
        }
        result = await self._graph.ainvoke(initial_state)
        return result

    # ------------------------------------------------------------------
    # Public API: stream execution
    # ------------------------------------------------------------------

    async def stream(
        self,
        query: str,
        project_id: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式执行 CRAG 管道，逐步输出节点结果。"""
        initial_state = {
            "query": query,
            "project_id": project_id,
            "conversation_history": conversation_history or [],
        }
        async for event in self._graph.astream(initial_state):
            yield event

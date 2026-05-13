from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from rag_qa.generator.citation_verifier import CitationVerifier
from rag_qa.generator.confidence_scorer import ConfidenceScorer
from rag_qa.generator.context_builder import ContextBuilder, RetrievedChunk
from rag_qa.generator.llm_client import LLMClient
from rag_qa.generator.prompt_templates import PromptTemplate


class SourceRef(BaseModel):
    source_id: str
    title: str
    section: str | None = None
    author: str | None = None
    relevance_score: float


class AnswerResult(BaseModel):
    answer: str
    sources: list[SourceRef]
    confidence: float
    is_low_confidence: bool
    context_used: int


class StreamChunk(BaseModel):
    type: str
    content: str | None = None
    metadata: dict[str, Any] | None = None


class AnswerGenerator:
    def __init__(
        self,
        llm_client: LLMClient,
        context_builder: ContextBuilder,
        citation_verifier: CitationVerifier,
        confidence_scorer: ConfidenceScorer,
    ):
        self.llm_client = llm_client
        self.context_builder = context_builder
        self.citation_verifier = citation_verifier
        self.confidence_scorer = confidence_scorer
        self.prompt_template = PromptTemplate()

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AnswerResult:
        context, source_mapping = self.context_builder.build_context(chunks)

        messages = self._build_messages(context, query, conversation_history)

        raw_answer = await self.llm_client.generate(messages)

        cleaned_answer, valid_citations = self.citation_verifier.verify(raw_answer, source_mapping)

        confidence = self.confidence_scorer.score(chunks, cleaned_answer, valid_citations, source_mapping)
        is_low = self.confidence_scorer.is_low_confidence(confidence)

        sources = self._build_sources(valid_citations, source_mapping)

        return AnswerResult(
            answer=cleaned_answer,
            sources=sources,
            confidence=confidence,
            is_low_confidence=is_low,
            context_used=len(source_mapping),
        )

    async def generate_stream(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        context, source_mapping = self.context_builder.build_context(chunks)

        messages = self._build_messages(context, query, conversation_history)

        full_answer = ""
        async for token in self.llm_client.generate_stream(messages):
            full_answer += token
            yield StreamChunk(type="content", content=token)

        cleaned_answer, valid_citations = self.citation_verifier.verify(full_answer, source_mapping)

        confidence = self.confidence_scorer.score(chunks, cleaned_answer, valid_citations, source_mapping)
        is_low = self.confidence_scorer.is_low_confidence(confidence)

        sources = self._build_sources(valid_citations, source_mapping)

        yield StreamChunk(
            type="metadata",
            metadata={
                "answer": cleaned_answer,
                "sources": [s.model_dump() for s in sources],
                "confidence": confidence,
                "is_low_confidence": is_low,
                "context_used": len(source_mapping),
            },
        )

        yield StreamChunk(type="done")

    def _build_messages(
        self,
        context: str,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.prompt_template.SYSTEM_PROMPT},
        ]

        if conversation_history:
            messages.extend(conversation_history)

        user_content = self.prompt_template.format_chat(context=context, query=query)
        messages.append({"role": "user", "content": user_content})

        return messages

    @staticmethod
    def _build_sources(
        valid_citations: list[str], source_mapping: dict[str, dict[str, Any]]
    ) -> list[SourceRef]:
        sources: list[SourceRef] = []
        for citation_id in valid_citations:
            info = source_mapping.get(citation_id)
            if info:
                sources.append(
                    SourceRef(
                        source_id=citation_id,
                        title=info["title"],
                        section=info.get("section"),
                        author=info.get("author"),
                        relevance_score=info.get("relevance_score", 0.0),
                    )
                )
        return sources

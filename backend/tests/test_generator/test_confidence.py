from __future__ import annotations

from rag_qa.generator.confidence_scorer import ConfidenceScorer
from rag_qa.generator.context_builder import RetrievedChunk


def _make_chunk(relevance_score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1",
        document_id="d1",
        project_id="p1",
        content="测试内容",
        title="Test Doc",
        relevance_score=relevance_score,
    )


def test_high_confidence():
    scorer = ConfidenceScorer()
    chunks = [_make_chunk(0.9), _make_chunk(0.85), _make_chunk(0.88)]
    answer = "根据文档[来源1]，系统支持多种格式[来源2]。具体包括PDF和Word[来源3]。详细说明请参考[来源1]。"
    source_mapping = {
        "1": {"chunk_id": "c1", "title": "Doc1"},
        "2": {"chunk_id": "c2", "title": "Doc2"},
        "3": {"chunk_id": "c3", "title": "Doc3"},
    }
    valid_citations = ["1", "2", "3"]
    score = scorer.score(chunks, answer, valid_citations, source_mapping)
    assert score >= 0.6
    assert not scorer.is_low_confidence(score)


def test_low_confidence():
    scorer = ConfidenceScorer()
    chunks = [_make_chunk(0.2), _make_chunk(0.1)]
    answer = "不太确定"
    source_mapping = {"1": {"chunk_id": "c1", "title": "Doc1"}}
    valid_citations: list[str] = []
    score = scorer.score(chunks, answer, valid_citations, source_mapping)
    assert score < 0.6
    assert scorer.is_low_confidence(score)


def test_no_citations():
    scorer = ConfidenceScorer()
    chunks = [_make_chunk(0.5)]
    answer = "这是一个没有引用的答案，包含一些信息内容。"
    source_mapping: dict = {}
    valid_citations: list[str] = []
    score = scorer.score(chunks, answer, valid_citations, source_mapping)
    assert 0.0 <= score <= 1.0
    assert scorer.is_low_confidence(score)

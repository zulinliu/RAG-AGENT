from __future__ import annotations

from rag_qa.retrieval.retriever import RetrievedChunk
from rag_qa.retrieval.rrf_fusion import RRFFusion


def _make_chunk(chunk_id: str, score: float, source: str = "test") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id="doc-1",
        project_id="proj-1",
        content=f"content of {chunk_id}",
        chunk_type="paragraph",
        score=score,
        source=source,
    )


def test_rrf_single_list():
    fusion = RRFFusion(k=60)
    chunks = [_make_chunk("c1", 0.9), _make_chunk("c2", 0.7), _make_chunk("c3", 0.5)]
    results = fusion.fuse([chunks])
    assert len(results) == 3
    assert results[0].chunk_id == "c1"
    assert results[0].score > results[1].score
    assert results[1].score > results[2].score


def test_rrf_multiple_lists():
    fusion = RRFFusion(k=60)
    list_a = [_make_chunk("c1", 0.9, "vector"), _make_chunk("c2", 0.7, "vector")]
    list_b = [_make_chunk("c2", 0.8, "bm25"), _make_chunk("c3", 0.6, "bm25")]
    results = fusion.fuse([list_a, list_b])
    assert len(results) == 3
    c2_result = next(r for r in results if r.chunk_id == "c2")
    c1_result = next(r for r in results if r.chunk_id == "c1")
    assert c2_result.score > c1_result.score


def test_rrf_same_chunk_id():
    fusion = RRFFusion(k=60)
    list_a = [_make_chunk("c1", 0.9, "vector"), _make_chunk("c2", 0.7, "vector")]
    list_b = [_make_chunk("c1", 0.8, "bm25"), _make_chunk("c3", 0.6, "bm25")]
    results = fusion.fuse([list_a, list_b])
    assert len(results) == 3
    c1_result = next(r for r in results if r.chunk_id == "c1")
    single_results = [r for r in results if r.chunk_id in ("c2", "c3")]
    assert c1_result.score > single_results[0].score

from __future__ import annotations

from rag_qa.generator.citation_verifier import CitationVerifier


def test_extract_citations():
    verifier = CitationVerifier()
    text = "根据文档[来源1]，系统支持多种格式[来源3]。详见[来源2]。"
    citations = verifier._extract_citations(text)
    assert citations == ["1", "3", "2"]


def test_verify_valid_citations():
    verifier = CitationVerifier()
    answer = "系统支持PDF[来源1]和Word[来源2]格式。"
    source_mapping = {
        "1": {"chunk_id": "c1", "title": "Doc1"},
        "2": {"chunk_id": "c2", "title": "Doc2"},
    }
    cleaned, valid = verifier.verify(answer, source_mapping)
    assert "1" in valid
    assert "2" in valid
    assert "[来源1]" in cleaned
    assert "[来源2]" in cleaned


def test_filter_invalid_citations():
    verifier = CitationVerifier()
    answer = "系统支持PDF[来源1]和Excel[来源99]格式。"
    source_mapping = {
        "1": {"chunk_id": "c1", "title": "Doc1"},
    }
    cleaned, valid = verifier.verify(answer, source_mapping)
    assert "1" in valid
    assert "99" not in valid
    assert "[来源1]" in cleaned
    assert "[来源99]" not in cleaned

from __future__ import annotations

from rag_qa.pipeline.chunker import ChineseChunker, ChunkStrategy
from rag_qa.schemas.metadata import DocumentSection, ParsedDocument


def _make_parsed_doc(content: str, sections: list[DocumentSection] | None = None) -> ParsedDocument:
    return ParsedDocument(
        doc_id="test-doc",
        title="Test Document",
        content=content,
        sections=sections or [],
        file_path="/tmp/test.txt",
        file_size=len(content),
        mime_type="text/plain",
        checksum="abc123",
    )


def test_chunk_strategy_default():
    strategy = ChunkStrategy()
    assert strategy.target_size == 800
    assert strategy.max_size == 1500
    assert strategy.min_size == 100
    assert strategy.overlap == 150
    assert "\n\n" in strategy.separators


def test_recursive_split():
    chunker = ChineseChunker(strategy=ChunkStrategy(target_size=100, max_size=150, overlap=0))
    long_text = "这是一段很长的文本。" * 50
    doc = _make_parsed_doc(long_text)
    results = chunker.chunk_document(doc)
    assert len(results) > 1
    for r in results:
        assert r.char_count <= 200


def test_semantic_boundary():
    chunker = ChineseChunker(strategy=ChunkStrategy(target_size=100, max_size=150, overlap=0))
    text = "这是一个完整的句子。后面还有内容"
    doc = _make_parsed_doc(text)
    results = chunker.chunk_document(doc)
    assert len(results) >= 1
    for r in results:
        assert r.content.strip() != ""


def test_overlap():
    chunker = ChineseChunker(strategy=ChunkStrategy(target_size=50, max_size=80, overlap=20))
    text = "第一段内容在这里。第二段内容在这里。第三段内容在这里。第四段内容在这里。"
    doc = _make_parsed_doc(text)
    results = chunker.chunk_document(doc)
    if len(results) > 1:
        for i in range(1, len(results)):
            prev_tail = results[i - 1].content[-20:]
            assert results[i].content[:20] == prev_tail or len(results[i - 1].content) <= 20

"""文档处理管道，编排完整的处理流程。"""

import asyncio
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chunker import ChineseChunker, Chunk, DocumentType
from .embedding import EmbeddingService
from .indexer import DualIndexer
from .parser import DocumentSection, SectionType, auto_parse

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """管道处理结果。"""

    document_id: str
    file_path: str
    status: str  # "success", "skipped", "error"
    chunk_count: int = 0
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class DocumentPipeline:
    """文档处理管道。

    编排完整的文档处理流程:
    下载 -> 解析 -> 清洗 -> 分块 -> 向量化 -> 双索引 -> 更新状态

    支持增量处理: 通过 checksum 判断文件是否需要重新处理。
    """

    def __init__(
        self,
        indexer: Optional[DualIndexer] = None,
        embedding_service: Optional[EmbeddingService] = None,
        chunker: Optional[ChineseChunker] = None,
    ) -> None:
        self.indexer = indexer or DualIndexer()
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunker = chunker or ChineseChunker()

    @classmethod
    def from_settings(cls, settings: Any) -> "DocumentPipeline":
        """Create a pipeline instance from application settings."""
        emb_cfg = settings.embedding
        embedding_svc = EmbeddingService(
            provider=emb_cfg.provider,
            api_url=emb_cfg.embed_endpoint,
            api_key=emb_cfg.api_key or None,
            model_name=emb_cfg.model_name,
            batch_size=emb_cfg.batch_size,
        )
        return cls(embedding_service=embedding_svc)

    def process_document(
        self,
        file_path: str,
        project_id: str,
        data_source_id: str,
        mime_type: Optional[str] = None,
        document_id: Optional[str] = None,
        local_file_path: Optional[str] = None,
    ) -> PipelineResult:
        """处理单个文档，执行完整的管道流程。

        Args:
            file_path: 原始文件路径（可能是远程路径标识符）
            project_id: 项目 ID
            data_source_id: 数据源 ID
            mime_type: 文件 MIME 类型（可选，自动检测）
            document_id: 文档 ID（可选，自动生成）
            local_file_path: 本地文件路径（如果已下载，否则使用 file_path）

        Returns:
            PipelineResult 处理结果
        """
        start_time = datetime.now()
        doc_id = document_id or str(uuid.uuid4())
        actual_path = local_file_path or file_path

        logger.info("开始处理文档: %s (project=%s, doc=%s)", actual_path, project_id, doc_id)

        try:
            # 步骤 1: 增量检测
            checksum = self._compute_checksum(actual_path)
            if self._is_processed(checksum, project_id):
                logger.info("文档未变更，跳过处理: %s", actual_path)
                return PipelineResult(
                    document_id=doc_id,
                    file_path=file_path,
                    status="skipped",
                    metadata={"checksum": checksum, "reason": "unchanged"},
                )

            # 步骤 2: 解析文档
            sections = auto_parse(actual_path, mime_type)
            if not sections:
                logger.warning("文档解析结果为空: %s", actual_path)
                return PipelineResult(
                    document_id=doc_id,
                    file_path=file_path,
                    status="error",
                    error_message="解析结果为空",
                )

            logger.info("解析完成: %d 个段落", len(sections))

            # 步骤 3: 文本清洗
            sections = self._clean_sections(sections)
            logger.info("清洗完成: %d 个段落", len(sections))

            # 步骤 4: 智能分块
            doc_type = ChineseChunker.detect_document_type(sections)
            chunker = ChineseChunker(doc_type=doc_type)

            chunks = chunker.chunk(sections)
            if not chunks:
                logger.warning("分块结果为空: %s", actual_path)
                return PipelineResult(
                    document_id=doc_id,
                    file_path=file_path,
                    status="error",
                    error_message="分块结果为空",
                )

            logger.info("分块完成: %d 个块 (type=%s)", len(chunks), doc_type.value)

            # 步骤 5: 向量化
            texts = [chunk.content for chunk in chunks]
            vectors = asyncio.run(self.embedding_service.encode(texts))
            logger.info("向量化完成: %d 个向量", len(vectors))

            # 步骤 6: 双索引写入
            chunk_dicts = [
                {
                    "content": chunk.content,
                    "metadata": {
                        **chunk.metadata,
                        "char_count": chunk.char_count,
                    },
                }
                for chunk in chunks
            ]
            indexed = self.indexer.index_chunks(
                chunks=chunk_dicts,
                vectors=vectors,
                project_id=project_id,
                document_id=doc_id,
                data_source_id=data_source_id,
                checksum=checksum,
            )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.info("文档处理完成: %s (%d 块, %.0fms)", actual_path, indexed, duration)

            return PipelineResult(
                document_id=doc_id,
                file_path=file_path,
                status="success",
                chunk_count=indexed,
                duration_ms=duration,
                metadata={
                    "checksum": checksum,
                    "sections": len(sections),
                    "chunks": len(chunks),
                    "doc_type": doc_type.value,
                },
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.error("文档处理失败: %s - %s", actual_path, e, exc_info=True)
            return PipelineResult(
                document_id=doc_id,
                file_path=file_path,
                status="error",
                error_message=str(e),
                duration_ms=duration,
            )

    def delete_document(self, document_id: str) -> bool:
        """删除文档及其所有索引数据。"""
        return self.indexer.delete_document(document_id)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_checksum(file_path: str) -> str:
        """计算文件的 SHA-256 校验和。"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def _is_processed(self, checksum: str, project_id: str) -> bool:
        """检查文档是否已经处理过（基于 checksum）。"""
        return self.indexer.check_document_processed(checksum, project_id)

    @staticmethod
    def _clean_sections(sections: List[DocumentSection]) -> List[DocumentSection]:
        """清洗文档段落。"""
        import re

        cleaned: List[DocumentSection] = []
        for section in sections:
            content = section.content

            # 去除多余空白
            content = re.sub(r"[ \t]+", " ", content)
            content = re.sub(r"\n{3,}", "\n\n", content)
            content = content.strip()

            # 跳过空内容（标题除外）
            if not content and section.section_type != SectionType.HEADING:
                continue

            cleaned.append(DocumentSection(
                title=section.title,
                content=content,
                section_type=section.section_type,
                level=section.level,
                metadata=section.metadata,
            ))

        return cleaned

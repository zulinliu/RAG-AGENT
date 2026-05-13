from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from rag_qa.schemas.metadata import ParsedDocument, SourceType


class DocumentMetadata(BaseModel):
    doc_id: str
    project_id: str
    datasource_id: str | None = None
    source: SourceType
    source_id: str
    title: str
    author: str | None = None
    file_path: str
    file_size: int
    mime_type: str
    checksum: str
    created_at: datetime | None = None
    modified_at: datetime | None = None


class MetadataExtractor:
    def extract_from_parsed(
        self,
        parsed_doc: ParsedDocument,
        project_id: str,
        datasource_id: str | None = None,
        source: SourceType = SourceType.LOCAL,
        source_id: str = "",
    ) -> DocumentMetadata:
        created_at: datetime | None = None
        modified_at: datetime | None = None

        meta = parsed_doc.metadata or {}
        raw_created = meta.get("created_at")
        raw_modified = meta.get("modified_at")

        if isinstance(raw_created, datetime):
            created_at = raw_created
        elif isinstance(raw_created, str):
            try:
                created_at = datetime.fromisoformat(raw_created)
            except (ValueError, TypeError):
                pass

        if isinstance(raw_modified, datetime):
            modified_at = raw_modified
        elif isinstance(raw_modified, str):
            try:
                modified_at = datetime.fromisoformat(raw_modified)
            except (ValueError, TypeError):
                pass

        return DocumentMetadata(
            doc_id=parsed_doc.doc_id,
            project_id=project_id,
            datasource_id=datasource_id,
            source=source,
            source_id=source_id,
            title=parsed_doc.title,
            author=parsed_doc.author,
            file_path=parsed_doc.file_path,
            file_size=parsed_doc.file_size,
            mime_type=parsed_doc.mime_type,
            checksum=parsed_doc.checksum,
            created_at=created_at,
            modified_at=modified_at,
        )

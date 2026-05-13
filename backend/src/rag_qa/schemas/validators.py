from __future__ import annotations

import hashlib
import mimetypes
import os

from rag_qa.connectors.base import FileMetadata


def validate_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_mime_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def convert_dingtalk_metadata(raw: dict) -> FileMetadata:
    return FileMetadata(
        source_id=raw.get("file_id", ""),
        file_path=raw.get("file_path", ""),
        file_name=raw.get("file_name", ""),
        file_size=raw.get("file_size", 0),
        mime_type=raw.get("mime_type", validate_mime_type(raw.get("file_name", ""))),
        modified_at=raw.get("modified_at"),
        author=raw.get("creator"),
        checksum=raw.get("checksum"),
    )


def convert_seafile_metadata(raw: dict) -> FileMetadata:
    return FileMetadata(
        source_id=raw.get("obj_id", ""),
        file_path=raw.get("path", ""),
        file_name=os.path.basename(raw.get("path", "")),
        file_size=raw.get("size", 0),
        mime_type=raw.get("mime_type", validate_mime_type(raw.get("path", ""))),
        modified_at=raw.get("last_modified"),
        author=raw.get("last_modifier"),
        checksum=raw.get("checksum"),
    )


def convert_nas_metadata(raw: dict) -> FileMetadata:
    return FileMetadata(
        source_id=raw.get("file_id", ""),
        file_path=raw.get("path", ""),
        file_name=raw.get("name", ""),
        file_size=raw.get("size", 0),
        mime_type=raw.get("mime_type", validate_mime_type(raw.get("name", ""))),
        modified_at=raw.get("mtime"),
        author=raw.get("owner"),
        checksum=raw.get("checksum"),
    )


def convert_local_metadata(raw: dict) -> FileMetadata:
    file_path = raw.get("path", "")
    return FileMetadata(
        source_id=raw.get("file_id", ""),
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size=raw.get("size", 0),
        mime_type=raw.get("mime_type", validate_mime_type(file_path)),
        modified_at=raw.get("mtime"),
        author=raw.get("owner"),
        checksum=raw.get("checksum"),
    )

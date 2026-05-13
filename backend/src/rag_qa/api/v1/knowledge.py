from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.api.deps import get_current_user, get_db, require_role
from rag_qa.core.exceptions import NotFoundException
from rag_qa.models.document import Document, DocumentStatus
from rag_qa.models.project import Project
from rag_qa.models.user import Role, User
from rag_qa.schemas.common import PageData, PageResponse, ResponseBase
from rag_qa.schemas.document import DocumentResponse

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["knowledge"])


async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException(message="Project not found")
    return project


@router.get("", response_model=PageResponse[DocumentResponse])
async def list_documents(
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(project_id, db)
    query = select(Document).where(Document.project_id == project_id)
    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size).order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PageResponse(
        data=PageData(
            items=[DocumentResponse.model_validate(d) for d in documents],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.get("/{document_id}", response_model=ResponseBase[DocumentResponse])
async def get_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException(message="Document not found")
    return ResponseBase(data=DocumentResponse.model_validate(document))


@router.delete("/{document_id}", response_model=ResponseBase)
async def delete_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN, Role.PROJECT_ADMIN),
):
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.project_id == project_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundException(message="Document not found")
    await db.delete(document)
    await db.commit()
    return ResponseBase()


@router.post("/upload", response_model=ResponseBase[DocumentResponse])
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    datasource_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(project_id, db)
    document = Document(
        project_id=project_id,
        datasource_id=datasource_id,
        title=file.filename or "untitled",
        file_path=f"uploads/{project_id}/{file.filename}",
        file_size=0,
        mime_type=file.content_type,
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return ResponseBase(data=DocumentResponse.model_validate(document))

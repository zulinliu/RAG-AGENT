from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.core.exceptions import ConflictException, NotFoundException
from rag_qa.models.project import Project, ProjectMember, ProjectMemberRole, ProjectStatus
from rag_qa.schemas.project import MemberAdd, ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def create(self, data: ProjectCreate) -> Project:
        project = Project(
            name=data.name,
            description=data.description,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def update(self, project_id: str, data: ProjectUpdate) -> Project:
        project = await self.db.get(Project, project_id)
        if project is None:
            raise NotFoundException(f"Project {project_id} not found")

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.status is not None:
            project.status = data.status

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: str) -> None:
        project = await self.db.get(Project, project_id)
        if project is None:
            raise NotFoundException(f"Project {project_id} not found")

        await self.db.delete(project)
        await self.db.commit()

    async def get(self, project_id: str) -> Project:
        project = await self.db.get(Project, project_id)
        if project is None:
            raise NotFoundException(f"Project {project_id} not found")
        return project

    async def list_projects(self, skip: int = 0, limit: int = 20) -> list[Project]:
        stmt = select(Project).offset(skip).limit(limit).order_by(Project.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_member(self, project_id: str, data: MemberAdd) -> ProjectMember:
        project = await self.db.get(Project, project_id)
        if project is None:
            raise NotFoundException(f"Project {project_id} not found")

        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == data.user_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise ConflictException(f"User {data.user_id} is already a member of project {project_id}")

        member = ProjectMember(
            project_id=project_id,
            user_id=data.user_id,
            role=data.role,
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_member(self, project_id: str, user_id: str) -> None:
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()
        if member is None:
            raise NotFoundException(f"Member {user_id} not found in project {project_id}")

        await self.db.delete(member)
        await self.db.commit()

    async def list_members(self, project_id: str) -> list[ProjectMember]:
        stmt = select(ProjectMember).where(ProjectMember.project_id == project_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

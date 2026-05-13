"""Project management service.

Handles project CRUD and soft-delete operations.
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import UserProject


class ProjectService:
    """Business logic for project management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_project(
        self,
        name: str,
        description: str | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project display name.
            description: Optional description text.

        Returns:
            The newly created ``Project``.
        """
        project = Project(
            name=name,
            description=description or "",
        )
        self._db.add(project)
        await self._db.flush()
        return project

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_project(self, project_id: uuid.UUID) -> Project:
        """Retrieve a project by ID.

        Raises:
            ValueError: If the project is not found or is soft-deleted.
        """
        project = await self._db.get(Project, project_id)
        if project is None or not project.is_active:
            raise ValueError(f"Project not found: {project_id}")
        return project

    async def list_projects(
        self,
        user_id: uuid.UUID | None = None,
    ) -> Sequence[Project]:
        """List active projects.

        Args:
            user_id: If provided, only return projects the user belongs to.

        Returns:
            List of active ``Project`` instances.
        """
        stmt = select(Project).where(Project.is_active == True)  # noqa: E712

        if user_id is not None:
            stmt = (
                stmt.join(UserProject, UserProject.project_id == Project.id)
                .where(UserProject.user_id == user_id)
            )

        stmt = stmt.order_by(Project.name)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_project(
        self,
        project_id: uuid.UUID,
        **kwargs: Any,
    ) -> Project:
        """Update mutable project fields.

        Acceptable keyword arguments: name, description.

        Raises:
            ValueError: If the project is not found.
        """
        project = await self.get_project(project_id)

        allowed_fields = {"name", "description"}
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(project, field, value)

        await self._db.flush()
        return project

    # ------------------------------------------------------------------
    # Delete (soft)
    # ------------------------------------------------------------------

    async def delete_project(self, project_id: uuid.UUID) -> None:
        """Soft-delete a project by setting ``is_active = False``.

        Raises:
            ValueError: If the project is not found.
        """
        project = await self.get_project(project_id)
        project.is_active = False
        await self._db.flush()

"""User management service.

Handles user CRUD, authentication, and project-role assignment.
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User, UserProject
from app.utils.auth import (
    create_access_token,
    get_password_hash,
    verify_password,
)


class UserService:
    """Business logic for user management and authentication."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
    ) -> User:
        """Create a new user with a bcrypt-hashed password.

        Args:
            username: Unique login name.
            email: Unique email address.
            password: Plaintext password (will be hashed).
            role: RBAC role string.

        Returns:
            The newly created ``User`` instance.

        Raises:
            ValueError: If the username or email is already taken.
        """
        existing = await self._db.execute(
            select(User).where(
                (User.username == username) | (User.email == email),
            ),
        )
        if existing.scalars().first() is not None:
            raise ValueError("Username or email already exists")

        user = User(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    # ------------------------------------------------------------------
    # Authenticate
    # ------------------------------------------------------------------

    async def authenticate(self, username: str, password: str) -> str:
        """Verify credentials and return a signed JWT token.

        Args:
            username: Login name.
            password: Plaintext password.

        Returns:
            Encoded JWT string.

        Raises:
            ValueError: On invalid credentials or inactive account.
        """
        result = await self._db.execute(
            select(User).where(User.username == username),
        )
        user = result.scalars().first()

        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")
        if not user.is_active:
            raise ValueError("User account is disabled")

        project_ids = [
            str(assoc.project_id) for assoc in user.project_associations
        ]

        token = create_access_token({
            "user_id": str(user.id),
            "username": user.username,
            "role": user.role,
            "project_ids": project_ids,
        })
        return token

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Retrieve a user by primary key.

        Raises:
            ValueError: If the user is not found.
        """
        user = await self._db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        return user

    async def get_user_by_username(self, username: str) -> User | None:
        """Look up a user by username. Returns ``None`` when absent."""
        result = await self._db.execute(
            select(User).where(User.username == username),
        )
        return result.scalars().first()

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[User], int]:
        """Return a paginated list of users and the total count."""
        count_result = await self._db.execute(
            select(sa_func.count()).select_from(User),
        )
        total = count_result.scalar() or 0

        result = await self._db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit),
        )
        users = result.scalars().all()
        return users, total

    async def get_user_projects(self, user_id: uuid.UUID) -> Sequence[Project]:
        """Return all projects the user is a member of."""
        result = await self._db.execute(
            select(Project)
            .join(UserProject, UserProject.project_id == Project.id)
            .where(
                UserProject.user_id == user_id,
                Project.is_active == True,  # noqa: E712
            )
            .order_by(Project.name),
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_user(self, user_id: uuid.UUID, **kwargs: Any) -> User:
        """Update mutable user fields.

        Acceptable keyword arguments: email, password, role, is_active.
        If ``password`` is provided it will be hashed automatically.

        Raises:
            ValueError: If the user is not found.
        """
        user = await self.get_user(user_id)

        allowed_fields = {"email", "password", "role", "is_active"}
        for field, value in kwargs.items():
            if field not in allowed_fields:
                continue
            if field == "password":
                user.password_hash = get_password_hash(value)
            else:
                setattr(user, field, value)

        await self._db.flush()
        return user

    # ------------------------------------------------------------------
    # Project role management
    # ------------------------------------------------------------------

    async def assign_project_role(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        role: str,
    ) -> UserProject:
        """Assign or update a user's role within a project.

        Raises:
            ValueError: If user or project is not found.
        """
        user = await self.get_user(user_id)
        project = await self._db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        result = await self._db.execute(
            select(UserProject).where(
                UserProject.user_id == user_id,
                UserProject.project_id == project_id,
            ),
        )
        existing = result.scalars().first()
        if existing is not None:
            existing.role = role
            await self._db.flush()
            return existing

        user_project = UserProject(
            user_id=user_id,
            project_id=project_id,
            role=role,
        )
        self._db.add(user_project)
        await self._db.flush()
        return user_project

    async def remove_project_role(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> None:
        """Remove a user's role within a project.

        Raises:
            ValueError: If the association does not exist.
        """
        result = await self._db.execute(
            select(UserProject).where(
                UserProject.user_id == user_id,
                UserProject.project_id == project_id,
            ),
        )
        association = result.scalars().first()
        if association is None:
            raise ValueError("User is not a member of this project")
        await self._db.delete(association)
        await self._db.flush()

    async def get_project_members(
        self,
        project_id: uuid.UUID,
    ) -> Sequence[UserProject]:
        """List all members of a project with their roles."""
        result = await self._db.execute(
            select(UserProject)
            .where(UserProject.project_id == project_id)
            .order_by(UserProject.created_at),
        )
        return result.scalars().all()

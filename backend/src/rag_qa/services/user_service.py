from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.core.exceptions import ConflictException, NotFoundException, UnauthorizedException
from rag_qa.core.security import get_password_hash, verify_password
from rag_qa.models.user import User
from rag_qa.schemas.user import UserCreate


class UserService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def create(self, data: UserCreate) -> User:
        stmt = select(User).where(User.username == data.username)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictException(f"Username {data.username} already exists")

        stmt = select(User).where(User.email == data.email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictException(f"Email {data.email} already exists")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=get_password_hash(data.password),
            display_name=data.display_name,
            role=data.role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.get_by_username(username)
        if user is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def get(self, user_id: str) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundException(f"User {user_id} not found")
        return user

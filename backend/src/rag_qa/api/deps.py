from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.core.exceptions import ForbiddenException, UnauthorizedException
from rag_qa.core.security import verify_token
from rag_qa.db.session import async_session_factory
from rag_qa.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = verify_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException(message="Invalid token payload")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedException(message="User not found")
    if not user.is_active:
        raise UnauthorizedException(message="User is inactive")
    return user


def require_role(*roles: Role):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException(
                message=f"Role '{current_user.role}' not allowed. "
                        f"Required: {[r.value for r in roles]}"
            )
        return current_user
    return Depends(role_checker)


class MilvusManager:
    _instance: MilvusManager | None = None

    def __init__(self) -> None:
        from rag_qa.core.config import settings
        self.host = settings.milvus.host
        self.port = settings.milvus.port
        self._connected = False

    @classmethod
    def get_instance(cls) -> MilvusManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False


class ESManager:
    _instance: ESManager | None = None

    def __init__(self) -> None:
        from rag_qa.core.config import settings
        self.hosts = settings.elasticsearch.hosts
        self._connected = False

    @classmethod
    def get_instance(cls) -> ESManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False


async def get_milvus_manager() -> MilvusManager:
    return MilvusManager.get_instance()


async def get_es_manager() -> ESManager:
    return ESManager.get_instance()

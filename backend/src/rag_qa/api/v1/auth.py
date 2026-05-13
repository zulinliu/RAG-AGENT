from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_qa.api.deps import get_current_user, get_db, require_role
from rag_qa.core.exceptions import BadRequestException, UnauthorizedException
from rag_qa.core.security import create_access_token, get_password_hash, verify_password
from rag_qa.models.user import Role, User
from rag_qa.schemas.common import ResponseBase
from rag_qa.schemas.user import Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ResponseBase[Token])
async def login(
    username: str,
    password: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedException(message="Incorrect username or password")
    if not user.is_active:
        raise UnauthorizedException(message="User is inactive")
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    access_token = create_access_token(data={"sub": user.id, "role": user.role.value})
    return ResponseBase(data=Token(access_token=access_token))


@router.post("/register", response_model=ResponseBase[UserResponse])
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(Role.SYSTEM_ADMIN),
):
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalar_one_or_none() is not None:
        raise BadRequestException(message="Username already exists")
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none() is not None:
        raise BadRequestException(message="Email already exists")
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        role=user_in.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ResponseBase(data=UserResponse.model_validate(user))


@router.get("/me", response_model=ResponseBase[UserResponse])
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return ResponseBase(data=UserResponse.model_validate(current_user))

"""Authentication and authorization utilities.

Provides JWT token creation/verification, password hashing,
and FastAPI dependency classes for RBAC permission checking.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload to encode. Should contain at minimum
              ``user_id``, ``username``, ``role``, ``project_ids``.
        expires_delta: Custom expiration time. Falls back to
              ``auth.access_token_expire_minutes``.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.auth.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),
    })
    return jwt.encode(
        to_encode,
        settings.auth.secret_key,
        algorithm=settings.auth.algorithm,
    )


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: Raw JWT string.

    Returns:
        Decoded token payload dictionary.

    Raises:
        HTTPException: When the token is expired, malformed, or invalid.
    """
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise credentials_exception from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """FastAPI dependency that extracts the current user from the JWT token.

    Checks the token blacklist (Redis) before accepting the token.

    Returns:
        Token payload dict with keys: user_id, username, role, project_ids.
    """
    payload = verify_token(token)

    # Check token blacklist in Redis
    jti: str | None = payload.get("jti")
    if jti is not None:
        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            is_revoked = await redis.get(f"token_blacklist:{jti}")
            if is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    user_id: str | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def revoke_token(
    token: str,
    request: Request,
) -> None:
    """Add a JWT token to the Redis blacklist.

    The token is stored with a TTL equal to its remaining validity period,
    so expired tokens are automatically cleaned up.
    """
    payload = verify_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        return

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        logger.warning("Redis unavailable; cannot revoke token")
        return

    # Calculate remaining TTL in seconds
    now = datetime.now(timezone.utc).timestamp()
    remaining_ttl = int(exp - now)
    if remaining_ttl > 0:
        await redis.set(f"token_blacklist:{jti}", "1", ex=remaining_ttl)


class PermissionChecker:
    """FastAPI dependency class that checks user role and project access.

    Usage::

        # Require system_admin role
        @router.get(
            "/",
            dependencies=[Depends(PermissionChecker(roles={"system_admin"}))],
        )

        # Require any of several roles
        @router.post(
            "/",
            dependencies=[Depends(
                PermissionChecker(roles={"system_admin", "project_admin"}),
            )],
        )

        # Require access to a specific project
        @router.get(
            "/{project_id}",
            dependencies=[Depends(PermissionChecker(project_access=True))],
        )
    """

    def __init__(
        self,
        roles: set[str] | None = None,
        project_access: bool = False,
    ) -> None:
        self._roles = roles
        self._project_access = project_access

    async def __call__(
        self,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role: str = current_user.get("role", "")

        # system_admin bypasses all role checks
        if user_role == "system_admin":
            return current_user

        if self._roles is not None and user_role not in self._roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        if self._project_access:
            project_ids = current_user.get("project_ids", [])
            if not project_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User has no project assignments",
                )

        return current_user


def check_project_permission(
    current_user: dict[str, Any],
    project_id: str,
) -> None:
    """Verify that the current user has access to the given project.

    Args:
        current_user: Decoded JWT payload.
        project_id: Target project identifier.

    Raises:
        HTTPException: 403 if the user does not have access.
    """
    user_role: str = current_user.get("role", "")
    if user_role == "system_admin":
        return

    project_ids: list[str] = current_user.get("project_ids", [])
    if project_id not in project_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this project",
        )

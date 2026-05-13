"""API router aggregation.

Combines all API route modules into a single top-level router with
the ``/api/v1`` prefix applied centrally.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.datasources import router as datasources_router
from app.api.documents import router as documents_router
from app.api.projects import router as projects_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api/v1")

# Authentication routes (already has /auth prefix internally)
api_router.include_router(auth_router)

# Project management routes (already has /projects prefix internally)
api_router.include_router(projects_router)

# User management routes (already has /users prefix internally)
api_router.include_router(users_router)

# Data source routes (use /projects/{id}/datasources and /datasources paths)
api_router.include_router(datasources_router)

# Document routes (use /projects/{id}/documents and /documents paths)
api_router.include_router(documents_router)

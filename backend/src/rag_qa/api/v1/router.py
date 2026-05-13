from fastapi import APIRouter

from rag_qa.api.v1.admin import router as admin_router
from rag_qa.api.v1.auth import router as auth_router
from rag_qa.api.v1.chat import router as chat_router
from rag_qa.api.v1.datasources import router as datasources_router
from rag_qa.api.v1.knowledge import router as knowledge_router
from rag_qa.api.v1.projects import router as projects_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(datasources_router)
api_router.include_router(chat_router)
api_router.include_router(knowledge_router)
api_router.include_router(admin_router)

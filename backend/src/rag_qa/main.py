from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_qa.api.deps import ESManager, MilvusManager
from rag_qa.api.v1.router import api_router
from rag_qa.core.config import settings
from rag_qa.core.exceptions import AppException
from rag_qa.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    milvus_mgr = MilvusManager.get_instance()
    es_mgr = ESManager.get_instance()
    await milvus_mgr.connect()
    await es_mgr.connect()
    yield
    await milvus_mgr.disconnect()
    await es_mgr.disconnect()
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.project.name,
        version=settings.project.version,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
            },
        )

    application.include_router(api_router)

    return application


app = create_app()

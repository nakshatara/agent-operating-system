from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.core.config import settings
from app.core.db import dispose_engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import TraceIdMiddleware
from app.core.redis import close_redis
from app.modules.agents.router import router as agents_router
from app.modules.audit.router import router as audit_router
from app.modules.dashboard.router import root_router as health_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.events.ws import router as ws_router
from app.modules.graph.client import close_driver
from app.modules.graph.router import router as graph_router
from app.modules.identity.router import auth_router, users_router
from app.modules.model_gateway.router import router as models_router
from app.modules.organizations.router import router as organization_router
from app.modules.runtime.router import router as runtime_router
from app.workers import WorkerSet

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    workers = WorkerSet()
    if settings.background_workers_enabled:
        workers.start()
        logger.info("background workers started")
    try:
        yield
    finally:
        await workers.shutdown()
        await close_driver()
        await close_redis()
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Agent Operating System API",
        version="0.1.0",
        description="Phase 1 foundation: identity, agent registry, lifecycle, runtime, graph, audit.",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TraceIdMiddleware)
    install_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    for r in (
        auth_router,
        users_router,
        organization_router,
        models_router,
        agents_router,
        runtime_router,
        graph_router,
        audit_router,
        dashboard_router,
        ws_router,
    ):
        api.include_router(r)
    app.include_router(api)
    app.include_router(health_router)
    return app


app = create_app()

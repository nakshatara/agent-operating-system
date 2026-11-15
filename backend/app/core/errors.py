from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import trace_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: Any | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str) -> AppError:
    return AppError(404, "not_found", f"{what} not found")


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def _envelope(request: Request, status: int, code: str, message: str, details: Any = None):
    trace_id = getattr(request.state, "trace_id", None) or trace_id_var.get()
    body = {"error": {"code": code, "message": message, "details": details, "trace_id": trace_id}}
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _envelope(request, exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return _envelope(
            request, 422, "validation_error", "Request validation failed", jsonable_encoder(exc.errors())
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError):
        logger.warning("integrity error on %s %s: %s", request.method, request.url.path, exc.orig)
        return _envelope(request, 409, "conflict", "The request conflicts with existing data")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return _envelope(request, 500, "internal_error", "Internal server error")

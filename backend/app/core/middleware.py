from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import trace_id_var

logger = logging.getLogger("app.access")
_SAFE = re.compile(r"[^A-Za-z0-9_\-]")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        trace_id = _SAFE.sub("", incoming)[:64] if incoming else ""
        trace_id = trace_id or uuid.uuid4().hex
        request.state.trace_id = trace_id
        token = trace_id_var.set(trace_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logger.info("%s %s %.1fms", request.method, request.url.path, elapsed)
            trace_id_var.reset(token)
        response.headers["X-Request-ID"] = trace_id
        return response

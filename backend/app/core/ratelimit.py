from __future__ import annotations

import logging
import time

from fastapi import Request

from app.core.config import settings
from app.core.errors import AppError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


async def auth_rate_limit(request: Request) -> None:
    """Fixed-window limiter (per client IP, per minute) for auth endpoints. Fails open if Redis is down.

    Note: behind a reverse proxy request.client is the proxy; configure proxy headers before relying on it.
    """
    ip = request.client.host if request.client else "unknown"
    key = f"rl:auth:{ip}:{int(time.time() // 60)}"
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 70)
    except Exception:  # noqa: BLE001 - limiter must not take auth down
        logger.warning("rate limiter unavailable (redis); failing open")
        return
    if count > settings.rate_limit_auth_per_minute:
        raise AppError(429, "rate_limited", "Too many attempts, try again in a minute")

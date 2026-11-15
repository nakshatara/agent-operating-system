from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.db import get_sessionmaker
from app.core.redis import get_redis
from app.core.security import InvalidToken, decode_token
from app.modules.events.fanout import channel_for
from app.modules.identity.models import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str = Query(...)) -> None:
    """Tenant-scoped live event stream. The channel is derived from the verified token, never from input."""
    try:
        claims = decode_token(token)
    except InvalidToken:
        await websocket.close(code=4401)
        return
    async with get_sessionmaker()() as db:
        user = await db.get(User, claims.user_id)
    if user is None or not user.is_active or user.organization_id != claims.org_id:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    pubsub = get_redis().pubsub()
    try:
        await pubsub.subscribe(channel_for(claims.org_id))
    except Exception:  # noqa: BLE001
        logger.warning("ws: redis unavailable")
        await websocket.close(code=1011)
        return

    async def pump() -> None:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                await websocket.send_text(str(message["data"]))

    async def watch_client() -> None:
        while True:
            await websocket.receive_text()  # raises WebSocketDisconnect on close; input is ignored

    tasks = [asyncio.create_task(pump()), asyncio.create_task(watch_client())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await pubsub.unsubscribe()
            await pubsub.aclose()
        except Exception:  # noqa: BLE001
            pass
        try:
            await websocket.close()
        except (RuntimeError, WebSocketDisconnect):
            pass

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from ..game.events import msg
from ..security import verify_token

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{room_code}")
async def game_socket(websocket: WebSocket, room_code: str, token: str = Query(default="")):
    manager = websocket.app.state.manager
    settings = websocket.app.state.settings
    code = room_code.strip().upper()
    await websocket.accept()  # accept first so the client can read our close code

    room = manager.get(code)
    if room is None:
        known = await manager.room_known(code)
        await websocket.close(code=4403 if known else 4404)
        return
    pid = verify_token(settings.secret_key, code, token)
    player = room.players.get(pid) if pid is not None else None
    if player is None or player.left:
        await websocket.close(code=4401)
        return

    await room.connect(pid, websocket)
    window_start, count = time.monotonic(), 0
    try:
        while True:
            raw = await websocket.receive_text()
            now = time.monotonic()
            if now - window_start > 10:
                window_start, count = now, 0
            count += 1
            if count > settings.ws_rate_limit_messages:
                await websocket.send_json(msg("error", code="rate_limited", message="Slow down."))
                continue
            if len(raw) > settings.ws_max_message_bytes:
                await websocket.send_json(msg("error", code="message_too_large", message="Message too large."))
                continue
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
            if not isinstance(data, dict):
                await websocket.send_json(msg("error", code="invalid_message", message="Send a JSON object."))
                continue
            await room.handle_message(pid, data)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.debug("websocket loop ended", exc_info=True)
    finally:
        await room.disconnect(pid, websocket)

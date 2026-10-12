"""Stateless HMAC session tokens binding a player to a room."""
from __future__ import annotations

import hashlib
import hmac


def _sig(secret: str, room_code: str, player_id: int) -> str:
    msg = f"{room_code}:{player_id}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def make_token(secret: str, room_code: str, player_id: int) -> str:
    return f"{player_id}.{_sig(secret, room_code, player_id)}"


def verify_token(secret: str, room_code: str, token: str) -> int | None:
    """Return the player id if the token is valid for this room, else None."""
    try:
        pid_s, sig = token.split(".", 1)
        pid = int(pid_s)
    except (ValueError, AttributeError):
        return None
    if hmac.compare_digest(sig, _sig(secret, room_code, pid)):
        return pid
    return None

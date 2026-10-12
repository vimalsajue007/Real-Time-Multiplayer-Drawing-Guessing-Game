"""Engine tests: drive GameRoom directly with fake sockets."""
import asyncio
import json

import pytest

from app import queries
from app.game import rules
from app.game.manager import GameManager
from app.game.room import Phase
from app.database import DbRunner, make_session_factory
from tests.conftest import make_settings


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed: int | None = None

    async def send_json(self, m):
        self.sent.append(m)

    async def close(self, code=1000, reason=None):
        self.closed = code

    def of(self, type_):
        return [m for m in self.sent if m["type"] == type_]


def contains_value(obj, needle) -> bool:
    if isinstance(obj, dict):
        return any(contains_value(v, needle) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(contains_value(v, needle) for v in obj)
    return obj == needle


async def wait_for(cond, timeout=5.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)


async def make_game(manager, n=3, rounds=2, start=True):
    room, host = await manager.create_room("Host", rounds)
    players = [host]
    for i in range(n - 1):
        _, p = await manager.join_room(room.code, f"Player{i}")
        players.append(p)
    wss = {}
    for p in players:
        ws = FakeWS()
        await room.connect(p.id, ws)
        wss[p.id] = ws
    for p in players[1:]:
        await room.handle_message(p.id, {"type": "ready", "payload": {"ready": True}})
    if start:
        await room.handle_message(host.id, {"type": "start_game", "payload": {}})
    return room, players, wss


def guess(room, pid, text):
    return room.handle_message(pid, {"type": "guess", "payload": {"text": text}})


async def test_start_requires_host_min_players_and_ready(manager):
    room, host = await manager.create_room("Host", 1)
    ws = FakeWS()
    await room.connect(host.id, ws)
    await room.handle_message(host.id, {"type": "start_game"})
    assert ws.of("error")[-1]["payload"]["code"] == "not_enough_players"

    _, p2 = await manager.join_room(room.code, "Guest")
    ws2 = FakeWS()
    await room.connect(p2.id, ws2)
    await room.handle_message(host.id, {"type": "start_game"})
    assert ws.of("error")[-1]["payload"]["code"] == "players_not_ready"
    await room.handle_message(p2.id, {"type": "start_game"})
    assert ws2.of("error")[-1]["payload"]["code"] == "not_host"

    await room.handle_message(p2.id, {"type": "ready", "payload": {"ready": True}})
    await room.handle_message(host.id, {"type": "start_game"})
    assert room.phase == Phase.DRAWING


async def test_secret_word_only_sent_to_drawer(manager):
    room, players, wss = await make_game(manager)
    r = room.round
    drawer_ws = wss[r.drawer_id]
    assert drawer_ws.of("round_started")[0]["payload"]["word"] == r.word
    for pid, ws in wss.items():
        if pid == r.drawer_id:
            continue
        assert not contains_value(ws.sent, r.word), "word leaked to a guesser"
        assert "word" not in ws.of("round_started")[0]["payload"]
        assert ws.of("round_started")[0]["payload"]["hint"] == rules.mask_word(r.word)
    # a guesser who reconnects mid-round must not get the word in the snapshot
    guesser = next(p for p in players if p.id != r.drawer_id)
    assert room.snapshot(guesser.id)["word"] is None
    assert room.snapshot(r.drawer_id)["word"] == r.word


async def test_correct_guess_scores_once_and_drawer_cannot_guess(manager):
    room, players, wss = await make_game(manager, n=4)
    r = room.round
    drawer = r.drawer_id
    g1, g2 = [p.id for p in players if p.id != drawer][:2]

    await guess(room, drawer, r.word)
    assert wss[drawer].of("error")[-1]["payload"]["code"] == "drawer_cannot_guess"
    assert room.players[drawer].score == 0

    await guess(room, g1, "definitely wrong")
    assert room.players[g1].score == 0
    assert wss[g2].of("chat")[-1]["payload"]["text"] == "definitely wrong"

    await guess(room, g1, r.word.upper())
    pts = room.players[g1].score
    assert 100 <= pts <= 200
    assert room.players[drawer].score == rules.drawer_points(1, 1)
    # the correct guess text must not be broadcast
    assert not any(m["type"] == "chat" and m["payload"]["text"].lower() == r.word for ws in wss.values() for m in ws.sent)

    # repeated scoring prevented
    await guess(room, g1, r.word)
    assert wss[g1].of("error")[-1]["payload"]["code"] == "already_guessed"
    assert room.players[g1].score == pts
    assert room.phase == Phase.DRAWING  # g2 hasn't guessed yet


async def test_round_ends_when_everyone_guessed_then_next_drawer(manager):
    room, players, wss = await make_game(manager, n=3, rounds=2)
    r1 = room.round
    for p in players:
        if p.id != r1.drawer_id:
            await guess(room, p.id, r1.word)
    assert room.phase == Phase.ROUND_END
    ended = wss[players[0].id].of("round_ended")[-1]["payload"]
    assert ended["word"] == r1.word and ended["reason"] == "all_guessed" and not ended["is_last"]
    await wait_for(lambda: room.phase == Phase.DRAWING and room.round_number == 2)
    assert room.round.drawer_id != r1.drawer_id
    assert room.round.strokes == []
    assert room.round.word != r1.word


async def test_guess_after_round_end_rejected(manager):
    room, players, wss = await make_game(manager, n=2, rounds=2)
    r = room.round
    g = next(p.id for p in players if p.id != r.drawer_id)
    await guess(room, g, r.word)
    assert room.phase == Phase.ROUND_END
    await guess(room, g, r.word)
    assert wss[g].of("error")[-1]["payload"]["code"] in ("round_inactive", "already_guessed")


async def test_time_up_ends_round(engine):
    mgr = GameManager(make_settings(round_seconds=1), DbRunner(make_session_factory(engine)))
    try:
        room, players, wss = await make_game(mgr, rounds=2)
        await wait_for(lambda: wss[players[0].id].of("round_ended"), timeout=4)
        assert wss[players[0].id].of("round_ended")[-1]["payload"]["reason"] == "time_up"
    finally:
        await mgr.shutdown()


async def test_strokes_only_from_drawer_and_validated(manager):
    room, players, wss = await make_game(manager)
    r = room.round
    drawer = r.drawer_id
    other = next(p.id for p in players if p.id != drawer)
    stroke = {"stroke_id": "s1", "tool": "brush", "color": "#ff0000", "size": 8, "points": [[0.1, 0.2], [0.3, 0.4]]}

    await room.handle_message(other, {"type": "stroke", "payload": stroke})
    assert wss[other].of("error")[-1]["payload"]["code"] == "not_drawer"

    bad = dict(stroke, points=[[2, 0.5]])
    await room.handle_message(drawer, {"type": "stroke", "payload": bad})
    assert wss[drawer].of("error")[-1]["payload"]["code"] == "invalid_payload"

    await room.handle_message(drawer, {"type": "stroke", "payload": stroke})
    assert len(wss[other].of("stroke")) == 1
    assert not wss[drawer].of("stroke")  # not echoed to the drawer
    assert room.round.strokes[0]["points"] == [[0.1, 0.2], [0.3, 0.4]]

    await room.handle_message(drawer, {"type": "clear_canvas"})
    assert wss[other].of("canvas_cleared") and room.round.strokes == []


async def test_clients_cannot_set_scores(manager):
    room, players, wss = await make_game(manager)
    p = players[1]
    for evt in ("set_score", "score", "scores_updated"):
        await room.handle_message(p.id, {"type": evt, "payload": {"score": 9999, "player_id": p.id}})
        assert wss[p.id].of("error")[-1]["payload"]["code"] == "unknown_event"
    await guess(room, p.id, "x")
    assert all(pl.score == 0 for pl in room.players.values())


async def test_drawer_disconnect_ends_round_after_grace_and_game_continues(manager):
    room, players, wss = await make_game(manager, n=3, rounds=2)
    r = room.round
    await room.disconnect(r.drawer_id, wss[r.drawer_id])
    other = next(p.id for p in players if p.id != r.drawer_id)
    await wait_for(lambda: wss[other].of("round_ended"), timeout=3)
    assert wss[other].of("round_ended")[-1]["payload"]["reason"] == "drawer_disconnected"
    await wait_for(lambda: room.phase == Phase.DRAWING and room.round_number == 2, timeout=3)
    assert room.round.drawer_id != r.drawer_id


async def test_drawer_reconnect_within_grace_resumes_with_canvas(manager):
    room, players, wss = await make_game(manager)
    r = room.round
    drawer = r.drawer_id
    stroke = {"stroke_id": "a", "tool": "brush", "color": "#000000", "size": 5, "points": [[0.5, 0.5]]}
    await room.handle_message(drawer, {"type": "stroke", "payload": stroke})
    old = wss[drawer]
    await room.disconnect(drawer, old)
    new = FakeWS()
    await room.connect(drawer, new)
    await asyncio.sleep(0.6)  # longer than the drawer grace period
    assert room.phase == Phase.DRAWING and room.round is r
    snap = new.of("state_sync")[0]["payload"]
    assert snap["word"] == r.word and len(snap["strokes"]) == 1 and snap["phase"] == "drawing"


async def test_replaced_connection_closes_old_socket(manager):
    room, players, wss = await make_game(manager)
    pid = players[1].id
    old, new = wss[pid], FakeWS()
    await room.connect(pid, new)
    assert old.closed == 4409
    await room.disconnect(pid, old)           # stale socket's disconnect is ignored
    assert room.players[pid].connected


async def test_everyone_disconnecting_does_not_leave_game_stuck(manager):
    room, players, wss = await make_game(manager, n=3, rounds=3)
    for p in players:
        await room.disconnect(p.id, wss[p.id])
    await wait_for(lambda: room.leaderboard is not None, timeout=6)
    assert room.phase == Phase.FINISHED


async def test_player_leaving_midgame_below_minimum_ends_game(manager):
    room, players, wss = await make_game(manager, n=2, rounds=3)
    await room.handle_message(players[1].id, {"type": "leave"})
    await wait_for(lambda: room.phase == Phase.FINISHED, timeout=3)
    assert wss[players[0].id].of("game_ended")


async def test_full_game_persists_to_database(manager):
    room, players, wss = await make_game(manager, n=3, rounds=2)
    words = []
    for rnd in (1, 2):
        await wait_for(lambda: room.phase == Phase.DRAWING and room.round_number == rnd)
        r = room.round
        words.append(r.word)
        for p in players:
            if p.id != r.drawer_id:
                await guess(room, p.id, r.word)
        await wait_for(lambda: room.phase in (Phase.ROUND_END, Phase.FINISHED))
    await wait_for(lambda: wss[players[0].id].of("game_ended"))
    ended = wss[players[0].id].of("game_ended")[-1]["payload"]
    assert ended["reason"] == "completed" and len(ended["leaderboard"]) == 3
    assert ended["leaderboard"][0]["rank"] == 1 and ended["leaderboard"][0]["is_winner"]

    detail = await manager.db.run(queries.game_detail, room.code)
    assert detail["status"] == "finished" and detail["started_at"] and detail["ended_at"]
    assert [r["word"] for r in detail["rounds"]] == words
    assert all(r["correct_guesses"] == 2 for r in detail["rounds"])
    assert sum(p["score"] for p in detail["players"]) == sum(pl.score for pl in room.players.values())
    assert any(p["is_winner"] for p in detail["players"])

    board = await manager.db.run(queries.leaderboard, 10)
    assert len(board) == 3
    stats = await manager.db.run(queries.player_stats, "Host")
    assert stats["games_played"] == 1 and stats["rounds_drawn"] == 1


async def test_lobby_disconnect_removes_player_after_grace_and_reassigns_host(engine):
    mgr = GameManager(make_settings(lobby_grace_seconds=0.2), DbRunner(make_session_factory(engine)))
    try:
        room, players, wss = await make_game(mgr, n=3, start=False)
        host = players[0]
        await room.disconnect(host.id, wss[host.id])
        await wait_for(lambda: wss[players[1].id].of("host_changed"), timeout=3)
        assert room.host_id in (players[1].id, players[2].id)
        assert wss[players[1].id].of("host_changed")
    finally:
        await mgr.shutdown()

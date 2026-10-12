"""WebSocket integration tests using Starlette's TestClient."""
import pytest
from starlette.websockets import WebSocketDisconnect


class Client:
    def __init__(self, ws):
        self.ws = ws
        self.log: list[dict] = []

    def send(self, type_, **payload):
        self.ws.send_json({"type": type_, "payload": payload})

    def until(self, type_, limit=60):
        for _ in range(limit):
            m = self.ws.receive_json()
            self.log.append(m)
            if m["type"] == type_:
                return m["payload"]
        raise AssertionError(f"never received {type_}")


def contains_value(obj, needle) -> bool:
    if isinstance(obj, dict):
        return any(contains_value(v, needle) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(contains_value(v, needle) for v in obj)
    return obj == needle


def setup_room(client, rounds=1):
    a = client.post("/api/rooms", json={"display_name": "Alice", "total_rounds": rounds}).json()
    b = client.post(f"/api/rooms/{a['room_code']}/join", json={"display_name": "Bob"}).json()
    return a, b


def url(room, token):
    return f"/ws/{room['room_code']}?token={token}"


def test_invalid_token_and_unknown_room_close_codes(client):
    a, _ = setup_room(client)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(url(a, "bad.token")) as ws:
            ws.receive_json()
    assert e.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws/ZZZZZ?token=x") as ws:
            ws.receive_json()
    assert e.value.code == 4404


def test_cannot_connect_to_inactive_room(client):
    a, _ = setup_room(client)
    for who in (a,):
        client.post(f"/api/rooms/{a['room_code']}/leave", headers={"Authorization": f"Bearer {who['token']}"})
    # second player still in room, so remove them too
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(url(a, a["token"])) as ws:
            ws.receive_json()
    assert e.value.code in (4401, 4403)


def test_full_game_over_websocket(client):
    a, b = setup_room(client, rounds=1)
    with client.websocket_connect(url(a, a["token"])) as wa, client.websocket_connect(url(b, b["token"])) as wb:
        A, B = Client(wa), Client(wb)
        sa, sb = A.until("state_sync"), B.until("state_sync")
        assert sa["phase"] == "lobby" and sb["you"] == b["player_id"]
        assert {p["name"] for p in sb["players"]} == {"Alice", "Bob"}

        B.send("start_game")                     # not the host
        assert B.until("error")["code"] == "not_host"
        A.send("start_game")                     # Bob not ready
        assert A.until("error")["code"] == "players_not_ready"

        B.send("ready", ready=True)
        assert A.until("player_ready")["ready"] is True
        A.send("start_game")

        ra, rb = A.until("round_started"), B.until("round_started")
        assert ra["drawer_id"] == a["player_id"]
        word = ra["word"]
        assert "word" not in rb and rb["hint"].count("_") >= 3

        # drawing is relayed as operations, only the drawer may draw
        B.send("stroke", stroke_id="b1", points=[[0.1, 0.1]])
        assert B.until("error")["code"] == "not_drawer"
        A.send("stroke", stroke_id="s1", tool="brush", color="#ff0000", size=10, points=[[0.1, 0.1], [0.2, 0.2]], end=True)
        st = B.until("stroke")
        assert st["points"] == [[0.1, 0.1], [0.2, 0.2]] and st["color"] == "#ff0000"

        A.send("guess", text=word)               # drawer cannot guess
        assert A.until("error")["code"] == "drawer_cannot_guess"
        B.send("guess", text="not the word zzz")
        assert A.until("chat")["text"] == "not the word zzz"
        B.send("guess", text=word)
        cg = B.until("correct_guess")
        assert cg["name"] == "Bob" and cg["points"] >= 100 and "text" not in cg

        scores = B.until("scores_updated")["scores"]
        assert {s["player_id"]: s["score"] for s in scores}[b["player_id"]] == cg["points"]
        ended = B.until("round_ended")
        assert ended["word"] == word and ended["is_last"] and ended["reason"] == "all_guessed"
        final = B.until("game_ended")
        assert final["leaderboard"][0]["name"] == "Bob" and final["leaderboard"][0]["is_winner"]

        # the secret word never reached the guesser before the round ended
        before_end = B.log[: next(i for i, m in enumerate(B.log) if m["type"] == "round_ended")]
        assert not contains_value(before_end, word)


def test_client_cannot_forge_scores_and_bad_json_is_rejected(client):
    a, b = setup_room(client)
    with client.websocket_connect(url(a, a["token"])) as wa:
        A = Client(wa)
        A.until("state_sync")
        A.send("set_score", score=10000)
        assert A.until("error")["code"] == "unknown_event"
        wa.send_text("not json")
        assert A.until("error")["code"] == "invalid_message"
        wa.send_text("[1,2,3]")
        assert A.until("error")["code"] == "invalid_message"


def test_reconnect_receives_state_sync_and_peers_notified(client):
    a, b = setup_room(client)
    with client.websocket_connect(url(a, a["token"])) as wa:
        A = Client(wa)
        A.until("state_sync")
        with client.websocket_connect(url(b, b["token"])) as wb:
            Client(wb).until("state_sync")
            assert A.until("player_connected")["player_id"] == b["player_id"]
        assert A.until("player_disconnected")["player_id"] == b["player_id"]
        with client.websocket_connect(url(b, b["token"])) as wb2:
            snap = Client(wb2).until("state_sync")
            assert snap["you"] == b["player_id"] and snap["phase"] == "lobby"
        # the lobby keeps Bob's seat during the grace period
        assert any(p["id"] == b["player_id"] for p in snap["players"])


def test_leave_event_removes_player_and_broadcasts(client):
    a, b = setup_room(client)
    with client.websocket_connect(url(a, a["token"])) as wa, client.websocket_connect(url(b, b["token"])) as wb:
        A, B = Client(wa), Client(wb)
        A.until("state_sync"), B.until("state_sync")
        B.send("leave")
        left = A.until("player_left")
        assert left["player_id"] == b["player_id"] and left["reason"] == "left"
    info = client.get(f"/api/rooms/{a['room_code']}").json()
    assert info["player_count"] == 1

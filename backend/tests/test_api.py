"""REST API tests."""


def create(client, name="Alice", rounds=2):
    r = client.post("/api/rooms", json={"display_name": name, "total_rounds": rounds})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_protocol(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    proto = client.get("/api/protocol").json()
    assert "stroke" in proto["client_events"] and "round_started" in proto["server_events"]


def test_openapi_docs_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/rooms", "/api/rooms/{room_code}/join", "/api/leaderboard", "/api/games/history"):
        assert p in paths


def test_create_room_returns_token_and_unique_code(client):
    a, b = create(client, "Alice"), create(client, "Bob")
    assert a["room_code"] != b["room_code"] and len(a["room_code"]) == 5
    assert a["token"] and a["room"]["status"] == "waiting" and a["room"]["total_rounds"] == 2
    assert "word" not in str(a).lower().replace("password", "")


def test_join_and_room_info(client):
    room = create(client)
    code = room["room_code"]
    j = client.post(f"/api/rooms/{code}/join", json={"display_name": "Bob"})
    assert j.status_code == 200 and j.json()["player_id"] != room["player_id"]
    info = client.get(f"/api/rooms/{code.lower()}").json()
    assert info["player_count"] == 2 and info["joinable"] is True
    assert {p["display_name"] for p in info["players"]} == {"Alice", "Bob"}
    assert "word" not in info and "token" not in str(info)


def test_duplicate_name_and_validation(client):
    code = create(client)["room_code"]
    dup = client.post(f"/api/rooms/{code}/join", json={"display_name": "alice"})
    assert dup.status_code == 409 and dup.json()["code"] == "name_taken"
    assert client.post(f"/api/rooms/{code}/join", json={"display_name": "x"}).status_code == 422
    assert client.post(f"/api/rooms/{code}/join", json={"display_name": "<script>"}).status_code == 422
    assert client.post("/api/rooms", json={"display_name": "Bob", "total_rounds": 99}).status_code == 422


def test_room_full(client):
    code = create(client)["room_code"]
    for n in ("B1", "B2", "B3"):
        assert client.post(f"/api/rooms/{code}/join", json={"display_name": n}).status_code == 200
    r = client.post(f"/api/rooms/{code}/join", json={"display_name": "B4"})
    assert r.status_code == 409 and r.json()["code"] == "room_full"


def test_unknown_room(client):
    assert client.get("/api/rooms/ZZZZZ").status_code == 404
    assert client.post("/api/rooms/ZZZZZ/join", json={"display_name": "Bob"}).status_code == 404


def test_cannot_join_inactive_room(client):
    room = create(client)
    code = room["room_code"]
    r = client.post(f"/api/rooms/{code}/leave", headers={"Authorization": f"Bearer {room['token']}"})
    assert r.status_code == 204  # last player leaves -> room abandoned
    j = client.post(f"/api/rooms/{code}/join", json={"display_name": "Bob"})
    assert j.status_code == 403 and j.json()["code"] == "room_inactive"
    assert client.get(f"/api/rooms/{code}").json()["status"] == "abandoned"


def test_leave_requires_valid_token(client):
    code = create(client)["room_code"]
    r = client.post(f"/api/rooms/{code}/leave", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_token_is_bound_to_room(client):
    a, b = create(client, "Alice"), create(client, "Bob")
    r = client.post(f"/api/rooms/{b['room_code']}/leave", headers={"Authorization": f"Bearer {a['token']}"})
    assert r.status_code == 401


def test_history_leaderboard_stats_empty(client):
    assert client.get("/api/games/history").json() == []
    assert client.get("/api/leaderboard").json() == []
    assert client.get("/api/players/Nobody/stats").status_code == 404


def test_running_game_details_are_hidden(client):
    code = create(client)["room_code"]
    assert client.get(f"/api/games/{code}").status_code == 403
    assert client.get("/api/games/ZZZZZ").status_code == 404

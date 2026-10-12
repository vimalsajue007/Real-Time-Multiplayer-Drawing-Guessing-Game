# Doodle Duel — Real-Time Multiplayer Draw & Guess

A browser-based multiplayer drawing and guessing game. One player draws a secret word on a shared canvas, everyone else races to guess it. All gameplay runs over **WebSockets**; persistent data (history, leaderboard, stats) goes through a **REST API** backed by **MySQL 8**.

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, WebSockets, SQLAlchemy 2, Pydantic 2, Alembic, MySQL 8.0 |
| Frontend | React 18, TypeScript, Vite, HTML Canvas, Axios, Material UI |
| Ops | Docker, Docker Compose, nginx |

---

## Quick start (Docker)

```bash
cp .env.example .env          # then edit passwords + SECRET_KEY
docker compose up --build
```

* Game UI: http://localhost:8080
* Swagger / OpenAPI: http://localhost:8000/docs (ReDoc: `/redoc`)
* WebSocket protocol reference (JSON): http://localhost:8000/api/protocol
* MySQL (for Workbench): `localhost:3306`, credentials from `.env`

Migrations run automatically when the backend container starts (`alembic upgrade head`).

## Local development

**Backend**
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                  
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173 (proxies /api and /ws to :8000)
```

Open the game in two browser windows (or one normal + one private window) to play against yourself.

## Tests

```bash
cd backend
pytest -q
```

Tests use an in-memory SQLite database, so no MySQL is needed. 43 tests cover:

| File | Scope |
|---|---|
| `tests/test_rules.py` | Unit tests: scoring (correctness / time / round number), guess matching, drawer rotation, ranking, hints |
| `tests/test_engine.py` | Round & game logic with fake sockets: word secrecy, duplicate-score prevention, drawer can't guess, timeout, all-guessed, drawer disconnect/reconnect, everyone leaving, persistence to DB |
| `tests/test_api.py` | REST API: create/join/leave, validation, conflicts, inactive rooms, token binding, history/leaderboard/stats, Swagger |
| `tests/test_ws.py` | WebSocket integration (real sockets via TestClient): full game flow, auth close codes, forged events, reconnect, leave |

---

## How a game works

1. **Create / join** (REST) → server returns a `player_id` and a signed `token`.
2. **Connect** the WebSocket: `/ws/{ROOM}?token=…` → server replies with a full `state_sync`.
3. **Lobby**: players toggle *ready*; the host can start once `MIN_PLAYERS` are connected and everyone is ready.
4. **Rounds**: the drawer rotates through players in join order. The server picks a word, sends it **only to the drawer**, starts the timer, and relays strokes.
5. **Round end** (time up, everyone guessed, or drawer lost): word revealed, results shown, canvas cleared, next drawer.
6. After `total_rounds` rounds: **final leaderboard**; the game is persisted to MySQL.

### Scoring

| Event | Points |
|---|---|
| Correct guess | `(100 + 100 × time_remaining/round_time) × (1 + 0.10 × (round − 1))` — faster is better, later rounds are worth more |
| Drawer | `40 × (1 + 0.10 × (round − 1))` per player who guesses correctly |

All scores are computed server-side in `app/game/rules.py`.

---

## WebSocket protocol

Every message, both directions: `{"type": "<event>", "payload": { … }}`.

**Client → server** (all payloads validated with Pydantic)

| type | payload | rules |
|---|---|---|
| `ping` | – | answered with `pong` |
| `ready` | `{ready: bool}` | lobby only |
| `start_game` | – | host only; min players connected + all ready |
| `stroke` | `{stroke_id, tool: brush\|eraser, color: "#rrggbb", size: 1–64, points: [[x,y]…≤200], end}` | drawer only, active round; coords normalised 0..1 |
| `clear_canvas` | – | drawer only |
| `guess` | `{text}` | not the drawer, round active, not already correct, ≤64 chars |
| `leave` | – | leaves permanently |

**Server → client**

`state_sync`, `player_joined`, `player_left`, `player_connected`, `player_disconnected`, `player_ready`, `host_changed`, `game_started`, `round_started`, `stroke`, `canvas_cleared`, `chat` (wrong guess), `correct_guess`, `scores_updated`, `timer` (every second), `round_ended`, `waiting_for_players`, `game_ended`, `error`, `pong`.

Full descriptions: `GET /api/protocol`.

**Close codes**: `4401` invalid token/not a member · `4403` room inactive · `4404` room not found · `4409` replaced by a newer connection.

### Drawing sync
The canvas is never sent as an image. The drawer streams **stroke operations** (batched every ~40 ms, normalised to 0..1). Each client — and the server, for late joiners/reconnects — keeps the ordered stroke list and can rebuild the identical drawing at any resolution. Strokes live only in memory and are discarded after the round; they are **never written to MySQL**.

---

## REST API

| Method & path | Purpose |
|---|---|
| `POST /api/rooms` | Create a room (caller becomes host) → `room_code`, `player_id`, `token` |
| `POST /api/rooms/{code}/join` | Join a room that is waiting in its lobby |
| `GET  /api/rooms/{code}` | Public room info (never contains the word) |
| `POST /api/rooms/{code}/leave` | Leave (header `Authorization: Bearer <token>`) |
| `GET  /api/games/history` | Completed games (paged) |
| `GET  /api/games/{code}` | Details of a completed game incl. rounds & words (403 while running) |
| `GET  /api/leaderboard` | All-time leaderboard (by display name) |
| `GET  /api/players/{name}/stats` | Games, wins, win rate, avg/best score, correct guesses, rounds drawn |
| `GET  /api/health`, `/api/protocol` | Liveness; WS reference |

## Database

Tables exactly as specified — `game_rooms`, `players`, `game_rounds`, `guesses` — managed by Alembic (`backend/alembic/versions/0001_initial.py`).
One additive column: `players.is_winner` (so winners are stored explicitly; ties produce several winners). Room statuses: `waiting`, `in_progress`, `finished`, `abandoned`.

---

## Disconnect handling

| Situation | Behaviour |
|---|---|
| Lobby player disconnects | Seat kept for `LOBBY_GRACE_SECONDS`; reconnect restores it, otherwise they're removed. Host is reassigned. Empty room → `abandoned`. |
| Guesser disconnects mid-game | Others continue; round ends early once all *connected* guessers are correct. After `RECONNECT_GRACE_SECONDS` they're marked left (score kept on the board). |
| **Drawer** disconnects | If they don't return within `DRAWER_GRACE_SECONDS` the round ends (`drawer_disconnected`), word is revealed, next drawer is picked. Reconnecting in time resumes with the word and the canvas intact. |
| Browser closed / network lost | Same as above. The client auto-reconnects with exponential backoff (1 s → 8 s) using the same token. |
| Too few players left | Game ends with the leaderboard (`not_enough_players`) — never stuck. Between rounds it waits briefly for reconnects; grace timers guarantee eventual progress. |
| Same player opens a second tab | Older socket is closed with `4409`. |
| Server restart | Live games are in memory, so stale `waiting`/`in_progress` rooms are marked `abandoned` on startup. |

## Security & validation checklist

* **Authoritative server** – every action is validated in `GameRoom` (right phase, right role, schema, length, rate). Clients can only send intents; there is no event that sets a score, and unknown events return `unknown_event`.
* **Secret word never leaks** – sent only to the drawer (`round_started`, drawer's `state_sync`). Guessers get a masked hint. A correct guess is announced without its text, and players who already guessed or the drawer can't post chat, so the word can't be relayed. REST responses never include words for running games (`/games/{code}` → 403 until finished). Words appear in history only after the game ends.
* **Unauthorized joins** – only rooms in `waiting` accept new players (`403 room_inactive` for finished/abandoned, `409 game_in_progress`, `409 room_full`, `409 name_taken`). WebSocket access requires an HMAC token bound to *that room*; tokens for other rooms are rejected (`4401`).
* **No repeat scoring** – one correct guess per player per round, enforced under a per-room `asyncio.Lock`.
* **Abuse limits** – message size cap, per-connection rate limit, ≤200 points per stroke message, bounded stored points, display names sanitised (2–20 chars, no `<>&"`/control chars).
* **Persistence is best-effort** – a database hiccup is logged but never freezes a live game.

> Note: the server keeps live state in one process, so run **one backend worker/instance** (Redis pub/sub would be the next step to scale horizontally).

## Configuration

All settings are environment variables — see [`.env.example`](.env.example) (game timings, limits, DB, CORS, secret key).

## Project layout

```
drawguess/
├─ docker-compose.yml  .env.example
├─ backend/
│  ├─ app/
│  │  ├─ main.py            app factory, CORS, error handler
│  │  ├─ config.py          settings
│  │  ├─ models.py          SQLAlchemy tables
│  │  ├─ persistence.py     write-side DB functions
│  │  ├─ queries.py         read-side (history, leaderboard, stats)
│  │  ├─ schemas.py         REST schemas (Swagger)
│  │  ├─ security.py        HMAC session tokens
│  │  ├─ game/
│  │  │  ├─ rules.py        scoring & round logic (pure)
│  │  │  ├─ room.py         WebSocket game engine (state machine)
│  │  │  ├─ manager.py      room registry
│  │  │  ├─ events.py       message models + protocol docs
│  │  │  └─ words.py
│  │  └─ routers/           rooms.py · stats.py · ws.py
│  ├─ alembic/              migrations
│  └─ tests/
└─ frontend/
   └─ src/
      ├─ App.tsx  useGameSocket.ts  gameReducer.ts  canvasStore.ts  api.ts  theme.ts
      └─ components/  JoinCreate · Lobby · GameRoom · DrawingCanvas · GuessPanel
                      PlayerList · Scoreboard · Timer · RoundResult · FinalLeaderboard · HallOfFame
```

## Requirement traceability

| Requirement | Where |
|---|---|
| Display name, create/join/leave, unique room code | `routers/rooms.py`, `game/manager.py` (5-char unambiguous code, DB-checked), `JoinCreate.tsx`, `leave` WS event + REST |
| Lobby: players, count, code, ready, start; min players | `Lobby.tsx`, `PlayerList.tsx`, `GameRoom._start_game` |
| Drawer selection, secret word to drawer only, timer, strokes broadcast | `GameRoom._start_round/_tick_loop/_handle_stroke` |
| Canvas: mouse, touch, brush size, eraser, clear; operations not images | `DrawingCanvas.tsx` (pointer events), `canvasStore.ts`, `StrokePayload` |
| Guessing validations | `GameRoom._handle_guess` |
| Scoring (correctness, time, round) + live scoreboard | `game/rules.py`, `Scoreboard.tsx` |
| Round management, final leaderboard | `_end_round/_after_result/_finish_game`, `RoundResult.tsx`, `FinalLeaderboard.tsx` |
| Disconnect handling | `GameRoom.connect/disconnect/_grace_expired/...`, `useGameSocket.ts` |
| Persistence (rooms, players, rounds, words, scores, winners, times) | `persistence.py`, `models.py`, migration `0001` |
| WS events & clear message structure | `game/events.py`, `/api/protocol`, this README |
| REST (create room, room info, history, leaderboard, stats) | `routers/rooms.py`, `routers/stats.py` |
| Frontend screens | `frontend/src/components/*` |
| Drawer clearly distinguished | coral banner + "✏️ You are drawing" + toolbar vs. violet banner + masked hint for guessers |
| Tests (unit, WS integration, API) | `backend/tests/` |
| Docker, `.env.example`, README, Swagger | `docker-compose.yml`, `*/Dockerfile`, `.env.example`, this file, `/docs` |

## Design notes — "bright energy, balanced"

A vivid violet / coral / sunshine / teal palette carries the energy (gradient headers, bold buttons, playful emoji, Fredoka headings), balanced by a calm off-white canvas, generous spacing, soft shadows and consistent 16 px rounding. Colour also carries meaning: **coral = you're drawing**, **violet = you're guessing**, **teal = success/correct**, **sun/coral timer = running out of time**.

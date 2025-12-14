docker run -d -p 6379:6379 redis:7-alpine
# Quiz App - Multiplayer Service

Socket.IO service for real-time lobbies/games, using Redis pub/sub and the main API for data.

---
## How to Run
- Recommended: `cd mini-version/bootstrap && ./start-local.sh` (brings up frontend, API, multiplayer, Mongo, Redis).
- Standalone dev: `cd backend/multiplayer && pip install -e .[dev] && cp .env.example .env && python -m server.main` (requires Redis + API at :5000).

---
## Config (env)
- `FLASK_PORT` (default 5001)
- `REDIS_HOST/REDIS_PORT`
- `API_HOST/API_PORT` (backend API, default 5000)
- `MIN_PLAYERS_TO_START`, `MAX_PLAYERS_PER_LOBBY`, `DEFAULT_QUESTION_TIMER`
- `REQUIRE_AUTHENTICATION` (JWT expected), `OPENAI_API_KEY` optional

Example `.env` for local dev:
```env
FLASK_PORT=5001
REDIS_HOST=localhost
REDIS_PORT=6379
API_HOST=localhost
API_PORT=5000
MIN_PLAYERS_TO_START=1
MAX_PLAYERS_PER_LOBBY=10
DEFAULT_QUESTION_TIMER=30
REQUIRE_AUTHENTICATION=true
# Optional
# OPENAI_API_KEY=sk-...
```

---
## Events (quick)
- Client → Server: `join_lobby`, `leave_lobby`, `start_game`, `submit_answer`
- Server → Client: `lobby_update`, `game_started`, `question`, `answer_result`, `game_ended`

---
## Structure
- `server/main.py` entrypoint
- `server/routes/` REST endpoints for lobby management
- `server/sockets/` Socket.IO event handlers
- `server/services/` game logic

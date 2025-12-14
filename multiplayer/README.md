# Quiz App - Multiplayer Service

Real-time multiplayer quiz game service using WebSocket (Socket.IO) and Redis pub/sub.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│  Multiplayer │────▶│    Redis     │
│  (Socket.IO) │     │   :5001      │     │   Pub/Sub    │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                    │
                            ▼                    │
                     ┌──────────────┐           │
                     │  Backend API │◀──────────┘
                     │    :5000     │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   MongoDB    │
                     └──────────────┘
```

### Components

1. **WebSocket Server (Port 5001)**: Handles real-time game events via Socket.IO
2. **REST API (Port 5001)**: Lobby management endpoints (`/api/lobby/*`)
3. **Redis**: Pub/sub for event distribution between services

## Quick Start

### Prerequisites
- Python 3.11+
- Redis server
- Backend API service running on port 5000

### Local Development

```bash
# Navigate to multiplayer directory
cd backend/multiplayer

# Install dependencies
pip install -e ".[dev]"

# Set environment variables
cp .env.example .env
# Edit .env as needed

# Start Redis (if not running)
docker run -d -p 6379:6379 redis:7-alpine

# Start the service
python -m server.main
```

### With Docker Compose

See `mini-version/bootstrap/docker-compose.yml` for full setup:

```bash
cd mini-version/bootstrap
./start-local.sh
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_PORT` | `5001` | Server port |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `API_HOST` | `backend-api` | Main backend hostname |
| `API_PORT` | `5000` | Main backend port |
| `MIN_PLAYERS_TO_START` | `1` | Minimum players to start game |
| `MAX_PLAYERS_PER_LOBBY` | `10` | Maximum players per lobby |
| `DEFAULT_QUESTION_TIMER` | `30` | Seconds per question |
| `REQUIRE_AUTHENTICATION` | `true` | Require JWT authentication |
| `OPENAI_API_KEY` | _(empty)_ | Optional: for AI-generated questions |

## WebSocket Events

### Client → Server

| Event | Payload | Description |
|-------|---------|-------------|
| `join_lobby` | `{lobby_code, user_id}` | Join a game lobby |
| `leave_lobby` | `{lobby_code}` | Leave current lobby |
| `submit_answer` | `{lobby_code, answer, time_remaining}` | Submit quiz answer |
| `start_game` | `{lobby_code}` | Host starts the game |

### Server → Client

| Event | Payload | Description |
|-------|---------|-------------|
| `lobby_update` | `{players, status, ...}` | Lobby state changed |
| `game_started` | `{total_questions}` | Game has begun |
| `question` | `{question, options, time}` | New question |
| `answer_result` | `{correct, score, ...}` | Answer feedback |
| `game_ended` | `{scores, winner}` | Game complete |

## API Endpoints

### Lobby Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/lobby/create` | Create new lobby |
| `POST` | `/api/lobby/join` | Join existing lobby |
| `GET` | `/api/lobby/{code}` | Get lobby status |
| `POST` | `/api/lobby/{code}/leave` | Leave lobby |
| `POST` | `/api/lobby/{code}/start` | Start game (host only) |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health status |

## Single-Player Mode

The service supports single-player "practice mode" by default (`MIN_PLAYERS_TO_START=1`).
This allows users to create a lobby and start a game alone for practice.

For true multiplayer-only mode, set `MIN_PLAYERS_TO_START=2` in your `.env`.

## Project Structure

```
multiplayer/
├── .env.example          # Environment configuration template
├── ci/                   # CI/CD configuration
│   └── app-dockerfile/   # Docker build configuration
├── scripts/              # Utility scripts
└── server/               # Main application code
    ├── main.py           # Entry point
    ├── routes/           # REST API routes
    ├── services/         # Business logic
    └── sockets/          # WebSocket event handlers
```

## Development

### Running Tests

```bash
cd backend/multiplayer
pytest tests/ -v
```

### Code Style

```bash
# Lint
ruff check server/

# Format
ruff format server/
```

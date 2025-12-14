# Quiz App - API Service

Flask REST API for auth, quiz generation, user stats, and leaderboard.

---
## How to Run
- Recommended: use the mini-version compose (`mini-version/bootstrap/start-local.sh`) to launch frontend, API, multiplayer, Mongo, and Redis together.
- Local dev entrypoint: `python src/python/main.py` (expects Mongo/Redis).

---
## Stack
- Flask + Gunicorn
- MongoDB for users/questions/leaderboard; Redis for caching and events
- JWT auth (optional Google OAuth verification)
- Optional OpenAI API for question generation and answer evaluation
- Prometheus metrics on `/metrics`

---
## Core Request Flow
- Routes live in `src/python/main.py`; they delegate to controllers/services which call repositories in `src/db/` for Mongo and `common/redis_client.py` for cache/pubsub.
- Auth: `/api/auth/google-login` verifies Google ID (if enabled), issues JWT, returns user profile + token. Protected routes validate JWT.
- Quiz: `/api/question/generate` builds a prompt, calls OpenAI when a key is set, returns a structured question. `/api/answer/evaluate` sends the user answer to OpenAI for scoring/feedback.
- History & stats: `/api/user/answers` persists attempts; `/api/user/profile` and `/api/user/performance` aggregate from Mongo (optionally cached in Redis).
- Leaderboard: `/api/user/leaderboard/enhanced` returns top 10 plus current user rank from Mongo.

---
## Key Endpoints
- Auth: `POST /api/auth/google-login`
- Quiz: `GET /api/all-subjects`, `POST /api/question/generate`, `POST /api/answer/evaluate`
- User: `GET /api/user/profile`, `GET /api/user/history`, `GET /api/user/performance`
- Leaderboard: `GET /api/user/leaderboard/enhanced`
- Health/metrics: `GET /api/health`, `GET /metrics`

---
## Config (env)
- `JWT_SECRET` (required)
- `REQUIRE_AUTHENTICATION` (default true; set false for guest-only local testing)
- `MONGO_URI`, `REDIS_URL`
- `GOOGLE_CLIENT_ID` (optional Google login)
- `OPENAI_API_KEY` (optional AI features)

---
## Dev Notes
- Tests: `pytest`
- API client lives in `frontend/react-app/src/api/quizAPI.js`
- Routes/controllers under `src/python/main.py` and `src/db/`
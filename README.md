# Quiz App - Backend Repository

Flask API for the Quiz App platform (auth, quiz generation, stats, leaderboard, multiplayer support).

---
## Related Repositories

- Frontend: https://github.com/liav-hasson/quiz-app-frontend
- GitOps: https://github.com/liav-hasson/quiz-app-gitops
- IaC: https://github.com/liav-hasson/quiz-app-iac
- Mini (local all-in-one): https://github.com/liav-hasson/quiz-app-mini

---
## How to Run 
Use the mini-version Docker Compose to start frontend, backend, multiplayer, Mongo, and Redis together:
- `cd mini-version/bootstrap && ./start-local.sh`
- App: http://localhost:3000, API: http://localhost:5000 (`/api/health`), Multiplayer: http://localhost:5001

---
## Stack & Capabilities
- Flask + Gunicorn
- MongoDB for users, questions, leaderboard data; Redis for caching/real-time
- JWT auth with optional Google OAuth 2.0 verification
- Optional OpenAI API for question generation and answer evaluation
- Prometheus metrics on `/metrics`

---
## Core Flow 
- Auth: frontend sends Google ID token → API verifies (optional) → issues JWT → frontend stores `quiz_user`.
- Quiz generation: frontend calls `/api/question/generate` → API calls OpenAI (if key set) or falls back to stored data → returns question payload.
- Answer evaluation: frontend posts to `/api/answer/evaluate` → API asks OpenAI for score/feedback → response returned; `/api/user/answers` can persist history.
- Profile/stats: `/api/user/profile`, `/api/user/history`, `/api/user/performance` aggregate Mongo data; Redis may cache hot paths.
- Leaderboard: `/api/user/leaderboard/enhanced` reads Mongo top 10 and current user rank.
- Multiplayer: clients hit API to create/join lobby, then use Socket.IO (multiplayer service) which also calls the API for data and Redis for pub/sub.

---
## Configuration (env)
- `JWT_SECRET` (required)
- `REQUIRE_AUTHENTICATION` (default true, set false for local guest testing)
- `MONGO_URI`, `REDIS_URL`
- `GOOGLE_CLIENT_ID` (used in prod, optional for local guest testing)
- `OPENAI_API_KEY` (optional; enable AI generation/evaluation—set it locally if you want AI features)

### Local dev (without compose)
Minimal env to run `python src/python/main.py` with local services:
```bash
export JWT_SECRET=dev-secret
export MONGO_URI=mongodb://localhost:27017/quiz
export REDIS_URL=redis://localhost:6379
# optional
export GOOGLE_CLIENT_ID=your-google-client-id
export OPENAI_API_KEY=your-openai-key
```

---
## Development Notes
- Run tests: `pytest`
- Local debug entrypoint: `src/python/main.py`
- API client in the frontend lives at `frontend/react-app/src/api/quizAPI.js`
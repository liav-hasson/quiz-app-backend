# Common Shared Library

Shared code for both API (`backend/api`) and Multiplayer (`backend/multiplayer`). Centralizes data access, auth, config, and utilities.

---
## What’s Here
- `database.py`, `redis_client.py` — Mongo/Redis clients
- `repositories/` — data access layer (User/Quiz/Question/etc.)
- `utils/ai/` — OpenAI question/eval helpers
- `utils/identity/` — Google token verification + JWT service
- `config.py` — Pydantic settings loader
- `rate_limiter.py` — basic request limiting

Use these modules from services instead of re-implementing connections or auth logic.

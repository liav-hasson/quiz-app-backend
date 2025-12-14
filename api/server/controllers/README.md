# Controllers

Business logic layer for the API. Routes call controllers; controllers call repositories/services and return DTOs.

Flow
- Routes (in `src/python/main.py`) handle HTTP and delegate here.
- Controllers validate input, orchestrate AI/auth/DB work, and shape responses.
- Data access goes through repositories in `common/repositories/`.
- Auth uses `common/utils/identity/token_service.py` and (when enabled) `google_verifier.py`.
- Quiz/answer flows use `common/utils/ai/` if `OPENAI_API_KEY` is set; otherwise they rely on stored quiz data.

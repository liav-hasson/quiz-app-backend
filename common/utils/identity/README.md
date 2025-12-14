# Identity & Authentication

Google ID token verification + JWT issuing/validation shared by API and multiplayer.

---
## Flow (high level)
1) Frontend sends Google ID token.
2) `google_verifier.py` verifies with Google.
3) User record is created/updated.
4) `token_service.py` issues our JWT; subsequent requests use it for auth.

---
## Files
- `google_verifier.py` — Google token validation
- `token_service.py` — JWT create/verify helpers

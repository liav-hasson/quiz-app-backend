# Repositories

Data-access layer for MongoDB collections (User, Quiz, Question, etc.) shared by API and multiplayer services.

---
## Purpose
- Keeps controllers clean by abstracting database queries
- Provides reusable query patterns across services
- Simplifies testing through mockable interfaces

---
## Contents
- `user_repository.py` - User CRUD and profile operations
- `quiz_repository.py` - Quiz session management
- `question_repository.py` - Question storage and retrieval

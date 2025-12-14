# Repositories

Data-access layer for Mongo (User, Quiz, Question, etc.) shared by API and multiplayer.

Why: keeps controllers clean, reuses queries, and is easy to mock in tests.

Usage example:
```python
from common.repositories.user_repository import UserRepository
user = UserRepository.get_by_id(user_id)
```

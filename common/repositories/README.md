# Repositories

This directory implements the Repository Pattern for data access.

## What is the Repository Pattern?

The Repository Pattern is a way to organize code that interacts with the database. Instead of writing database queries (like `find`, `insert`, `update`) directly inside your API routes or controllers, you put them in a dedicated "repository" class.

## Why do we use it?

1. **Clean Code**: It keeps our business logic (controllers) clean and focused on what the app does, rather than how to fetch data.
2. **Reusability**: If multiple parts of the app need to find a user by ID, they can all call `UserRepository.get_by_id()` instead of rewriting the query.
3. **Testing**: It makes it easier to test the app. We can mock the repository to return fake data without needing a real database connection during tests.

## How to use it

Each major data model (like User, Quiz, Question) has its own repository file here.

Example usage in a controller:

```python
from common.repositories.user_repository import UserRepository

def get_profile(user_id):
    # We don't worry about MongoDB syntax here
    user = UserRepository.get_by_id(user_id)
    if not user:
        return None
    return user
```

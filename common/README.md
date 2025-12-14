# Common Shared Library

This directory contains shared code used by both the API Service (backend/api) and the Multiplayer Service (backend/multiplayer). By sharing these modules, we ensure consistency in database access, authentication, and utility functions across the entire backend architecture.

## Directory Structure

- **database.py**: Manages the MongoDB connection using pymongo. It handles connection pooling and provides a singleton instance for database access.
- **redis_client.py**: Manages the Redis connection. This is crucial for:
  - **Pub/Sub**: Broadcasting events between services (e.g., when a game starts).
  - **Caching**: Storing transient game state and session data.
- **repositories/**: Implements the Repository Pattern. Instead of writing raw database queries in controllers, we use repositories to abstract data access. This makes the code cleaner and easier to test.
- **utils/**: General utility modules for:
  - **ai/**: Integration with OpenAI for generating questions and evaluating answers.
  - **identity/**: Authentication logic, including JWT token generation/validation and Google OAuth verification.
  - **config.py**: Centralized configuration management using Pydantic settings.
  - **rate_limiter.py**: Logic to limit API requests and prevent abuse.

## Key Concepts

### Repository Pattern
We use repositories to decouple business logic from data access.
**Example:**
Instead of `db.users.find_one({"_id": user_id})`, we use `UserRepository.get_user_by_id(user_id)`.

### Authentication
Authentication is handled via JWT (JSON Web Tokens).
1. **Google OAuth**: The frontend sends a Google ID token.
2. **Verification**: GoogleTokenVerifier checks the token with Google.
3. **Session**: TokenService issues our own JWT for session management.

### AI Integration
The ai module handles prompts to OpenAI. It includes retry logic and structured output parsing to ensure the quiz questions are always in the correct format.

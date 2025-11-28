# Quiz-app Backend Repository 

####

---

## About The Quiz-app Project

The Quiz-app is a DevOps learning platform build by a DevOps student.
The app lets the user select a category, a sub-category and a difficulty, then generates a question about a random keyword in that subject. The user then answers the question, and recieves a score, and short feedback.

All the code is fully open source, and contains 5 main repositories:
- **[Frontend repository](https://github.com/liav-hasson/quiz-app-frontend.git)** - React frontend that runs on Nginx.
- **[Backend repository](https://github.com/liav-hasson/quiz-app-backend.git) << You are here!** - Flask Python backend logic.
- **[GitOps repository](https://github.com/liav-hasson/quiz-app-gitops.git)** - ArgoCD App-of-app pattern.
- **[IaC repository](https://github.com/liav-hasson/quiz-app-iac.git)** - Terraform creates oll the base infrastructure, on AWS.
- **[Mini-version repository](https://github.com/liav-hasson/quiz-app-mini.git)** - Allows you to self-host localy, or on AWS.

---

## Backend Architecture

### Tech Stack
- **Framework**: Flask (Python 3.13)
- **Database**: MongoDB (4 collections: `users`, `quiz_data`, `questions`, `top_ten`)
- **Authentication**: Google OAuth 2.0 with JWT token issuance
- **AI Integration**: OpenAI API for question generation and answer evaluation
- **Monitoring**: Prometheus metrics exported on `/metrics` endpoint
- **AWS Integration**: SSM Parameter Store for secure credential management, boto3 client

### Project Structure
```
src/
├── python/
│   ├── main.py              # Flask app & API endpoints
│   ├── config.py            # Configuration settings
│   ├── validation.py        # Input validation helpers
│   ├── quiz_utils.py        # Quiz logic utilities
│   └── ai_utils.py          # OpenAI integration
├── db/
│   ├── dbcontroller.py      # MongoDB connection & base controller
│   ├── user_controller.py   # User management (auth, profile, stats)
│   ├── quiz_controller.py   # Quiz data (topics, keywords, style)
│   ├── questions_controller.py  # Answer tracking & statistics
│   ├── topten_controller.py # Leaderboard management
│   ├── migrator.py          # JSON to MongoDB data migration
│   └── __init__.py          # Package exports
├── tests/
│   ├── test_main.py         # API endpoint tests
│   ├── test_auth.py         # OAuth & JWT tests
│   ├── test_quiz_utils.py   # Quiz utility tests
│   ├── test_validation.py   # Validation logic tests
│   └── conftest.py          # Pytest configuration & fixtures
└── requirements.txt         # Python dependencies

```

### Database Collections

#### 1. `users`
Stores user accounts and performance metrics.
```
{
  "_id": ObjectId,
  "username": string,
  "email": string,
  "name": string,
  "profile_picture": string (URL),
  "google_id": string,
  "experience": number (accumulated score),
  "questions_count": number (total attempts),
  "created_at": datetime,
  "updated_at": datetime
}
```

#### 2. `quiz_data`
Quiz content (topics, subtopics, keywords, style modifiers).
```
{
  "_id": ObjectId,
  "topic": string,
  "subtopic": string,
  "keywords": [string],
  "style_modifiers": [string],
  "created_at": datetime,
  "updated_at": datetime
}
```

#### 3. `questions`
Answer history for statistics and learning analytics.
```
{
  "_id": ObjectId,
  "user_id": string,
  "username": string,
  "question_text": string,
  "keyword": string,
  "category": string,
  "subject": string,
  "difficulty": number (1-3),
  "ai_generated": boolean,
  "extra": {
    "user_answer": string,
    "is_correct": boolean,
    "score": number
  },
  "created_at": datetime,
  "updated_at": datetime
}
```

#### 4. `top_ten`
Leaderboard entries (top 10 users by average score).
```
{
  "_id": ObjectId,
  "username": string,
  "score": number (exp / questions_count ratio),
  "meta": {
    "exp": number,
    "count": number
  },
  "created_at": datetime,
  "updated_at": datetime
}
```

---

## API Endpoints

> **Full API documentation**: See `BACKEND_DEV_GUIDE.md` in the project root for complete endpoint specifications, request/response schemas, and implementation status.

### Authentication
- **`POST /api/auth/google-login`** - Verify Google ID token and issue JWT
  - Input: `{credential: "<Google ID token>"}` 
  - Output: `{email, name, picture, token}`

### Quiz Generation
- **`GET /api/all-subjects`** - List all categories with subcategories (cached 30m)
- **`POST /api/question/generate`** - Generate AI-powered question
  - Input: `{category, subject, difficulty}`
  - Output: Generated question with keyword, difficulty, style
- **`POST /api/answer/evaluate`** - Get AI feedback on answer
  - Input: `{question, answer, difficulty}`
  - Output: Score (0-10) and feedback
- **`POST /api/user/answers`** - Save answer to history
  - Input: `{user_id, username, question, answer, difficulty, category, subject, score}`
  - Returns: `answer_id`

### Profile & Statistics
- **`GET /api/user/profile`** - Unified user stats + level progress (cached 5m)
  - Returns: XP, level, levelProgress, bestCategory, averageScore, streak, totalAnswers
- **`GET /api/user/history`** - Answer history with pagination
  - Query: `limit` (≤100), `before` (timestamp)
  - Returns: Array of answers with summary + details
- **`GET /api/user/performance`** - Aggregated performance data for charts
  - Query: `period` (7d/30d/90d/all), `granularity` (day/week/month)
  - Returns: Time buckets with scores + top categories

### Leaderboard
- **`GET /api/user/leaderboard/enhanced`** - Top 10 users + current user rank
  - Returns: `{topTen: [...], userRank: number}`

### Health & Monitoring
- **`GET /api/health`** - Health check (DB status)
- **`GET /metrics`** - Prometheus metrics

---

## Setup & Installation

### Prerequisites
- Python 3.13+
- MongoDB 5.0+
- OpenAI API key
- Google OAuth credentials (for authentication)

### Local Development

1. **Clone and install dependencies:**
```bash
git clone https://github.com/liav-hasson/quiz-app-backend.git
cd quiz-app-backend
python -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt
```

2. **Set environment variables:**
```bash
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export OPENAI_API_KEY=sk-...
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
export JWT_SECRET=your-secret-key
export JWT_EXP_DAYS=7
```

3. **Start MongoDB:**
```bash
mongod --dbpath /path/to/data
```

4. **Run the app:**
```bash
python src/python/main.py
```

The server will start on `http://localhost:5000`.

### Docker

```bash
docker build -t quiz-app-backend:latest -f ci/app-dockerfile/Dockerfile .
docker run -e MONGODB_HOST=host.docker.internal -p 5000:5000 quiz-app-backend:latest
```

### Kubernetes

See the [GitOps repository](https://github.com/liav-hasson/quiz-app-gitops.git) for Helm charts and ArgoCD deployment manifests.

---

## Features

### ✅ Current Features
- **Google OAuth 2.0** - Seamless user authentication via Google accounts
- **JWT Tokens** - Secure, stateless authentication with configurable expiration
- **Question Generation** - AI-powered question creation with OpenAI GPT
- **Answer Evaluation** - Automatic grading and feedback via OpenAI
- **User Statistics** - Track XP, answer counts, and performance metrics
- **Leaderboard** - Top 10 ranking + user position
- **MongoDB Integration** - Scalable NoSQL database with 4 collections
- **Data Migration** - Auto-import quiz data from `db.json` on first run
- **Prometheus Metrics** - Built-in observability for monitoring
- **AWS SSM Integration** - Secure credential management in production

### 🚧 In Progress (See `BACKEND_DEV_GUIDE.md`)
- **Profile API** - Unified stats endpoint with level system
- **Enhanced History** - Structured summary + details response
- **Performance API** - Time-based aggregation for charts
- **Rate Limiting** - Flask-Limiter for abuse protection
- **Security Headers** - Flask-Talisman hardening
- **Database Indexes** - Query optimization for user stats

### 🚀 Planned Features (See `BACKEND_DEV_GUIDE.md` Future Roadmap)
- **Achievements System** - Badge unlock endpoints
- **Levels API** - Progressive XP curve definitions
- **Feedback System** - User product feedback collection
- **Admin Tools** - Moderation and management endpoints
- **Extended Leaderboards** - Category/time filters + pagination
- **Structured Logging** - JSON logs for observability
- **Sentry Integration** - Error tracking and monitoring


## Testing

Run the test suite:
```bash
pytest -q                    # Quick run
pytest -v                    # Verbose output
pytest --cov                 # With coverage report
pytest src/tests/test_auth.py  # Specific test file
```

---

## Development Notes

### Controllers
Each MongoDB collection has a dedicated controller in `src/db/`:
- `UserController` - User CRUD, OAuth integration, experience tracking
- `QuizController` - Quiz data import/export, keyword/style management
- `QuestionsController` - Answer history & statistics storage
- `TopTenController` - Leaderboard queries and updates

### Error Handling
- Validation errors return `400 Bad Request` with error message
- Not found errors return `404 Not Found`
- Server errors return `500 Internal Server Error` with logs
- All endpoints log to stdout (configurable via config.py)

### Configuration
Edit `src/python/config.py` to customize:
- Flask debug mode & host/port
- Log levels
- Database defaults
- Feature flags

---

## Contributing

To contribute to this backend:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes and add tests
4. Run `pytest` to ensure all tests pass
5. Push and open a pull request

---

---

## Documentation

- **`README.md`** (project root) - High-level architecture, unified task board, API reference
- **`BACKEND_DEV_GUIDE.md`** - Complete backend guide (endpoints, tasks, ops, roadmap)
- **`FRONTEND_DEV_GUIDE.md`** - Frontend integration dependencies and blocked tasks

For detailed implementation specs, database schemas, and cross-team coordination, see the project root documentation.

---

## License

This project is open source. See LICENSE file for details.

---

## Support & Contact

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/liav-hasson/quiz-app-backend/issues)
- Check existing documentation in the repo
- Review related repositories for context
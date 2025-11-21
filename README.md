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

### Authentication
- **`POST /api/auth/google-login`** - Verify Google ID token and issue application JWT (recommended)
  - Input: `{credential: "<Google ID token>"}` 
  - Output: `{email, name, picture, token}`
- **`GET /api/auth/callback`** - OAuth redirect callback (returns JWT token & user)

### Quiz Generation
- **`GET /api/categories`** - List all quiz categories
- **`GET /api/subjects?category={name}`** - List subcategories for a category
- **`POST /api/question/generate`** - Generate a random question
  - Input: `{category, subject, difficulty}`
  - Output: Generated question with keyword, difficulty, style modifier
- **`POST /api/answer/evaluate`** - Get feedback on user's answer
  - Input: `{question, answer, difficulty}`
  - Output: Score and feedback from OpenAI

### User & Statistics
- **`POST /api/answers`** - Save user's answer for statistics tracking
  - Input: `{user_id, username, question, answer, difficulty, category, subject, score, is_correct}`
  - Increments user's `experience` and `questions_count`
  - Returns: `answer_id`

### Leaderboard
- **`GET /api/leaderboard`** - Fetch top 10 users by average score
  - Returns: Top 10 sorted by `experience / questions_count`
- **`POST /api/leaderboard/update`** - Update user's leaderboard position
  - Input: `{user_id, username}`
  - Calculates: `avg_score = experience / questions_count`
  - Returns: Updated average score & metadata

### Health & Monitoring
- **`GET /api/health`** - Health check (returns DB status)
- **`GET /metrics`** - Prometheus metrics (auto-generated by Flask exporter)

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
- **User Statistics** - Track experience points and question attempt counts
- **Leaderboard** - Real-time ranking by average score (exp / count ratio)
- **MongoDB Integration** - Scalable NoSQL database with 4 collections
- **Data Migration** - Auto-import quiz data from `db.json` on first run
- **Prometheus Metrics** - Built-in observability for monitoring
- **AWS SSM Integration** - Secure credential management in production

### 🚀 Planned/Future Features
- JWT-protected endpoints (middleware for auth)
- User profile updates & preference management
- Category-specific leaderboards
- Quiz session history and analytics dashboard
- Question difficulty adaptive learning
- Multi-language support
- Offline mode with local caching.


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

## License

This project is open source. See LICENSE file for details.

---

## Support & Contact

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/liav-hasson/quiz-app-backend/issues)
- Check existing documentation in the repo
- Review related repositories for context
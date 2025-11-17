# Quiz App Backend Architecture

## 📁 Project Structure (Bomt-React Style)

```
quiz-app-backend/
├── server/                  # Backend application
│   ├── models/              # Database layer (MongoDB controllers)
│   │   ├── __init__.py
│   │   ├── dbcontroller.py
│   │   ├── user_controller.py
│   │   ├── quiz_controller.py
│   │   ├── questions_controller.py
│   │   ├── topten_controller.py
│   │   └── migrator.py
│   │
│   ├── controllers/         # Business logic layer
│   │   ├── __init__.py
│   │   ├── quiz_controller.py
│   │   ├── auth_controller.py
│   │   └── user_activity_controller.py
│   │
│   ├── routes/              # API routes layer
│   │   ├── __init__.py
│   │   ├── health_routes.py
│   │   ├── quiz_routes.py
│   │   ├── auth_routes.py
│   │   └── user_activity_routes.py
│   │
│   ├── utils/               # Utility modules
│   │   ├── __init__.py
│   │   ├── ai_utils.py
│   │   ├── quiz_utils.py
│   │   ├── validation.py
│   │   └── config.py
│   │
│   ├── tests/               # Test files
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_main.py
│   │   ├── test_quiz_utils.py
│   │   └── test_validation.py
│   │
│   ├── server.py            # Main application entry point
│   ├── requirements.txt     # Python dependencies
│   └── .gitignore
│
├── ci/                      # CI/CD configurations
│   └── app-dockerfile/
│       ├── Dockerfile
│       └── .dockerignore
│
├── scripts/                 # Deployment/utility scripts
├── pyproject.toml          # Project metadata
└── README.md

```

## 🏗️ Architecture Pattern

### **3-Layer Architecture**

```
┌─────────────────────────────────────────────────────────┐
│                      Routes Layer                        │
│  (API Endpoints, Request/Response, Validation)          │
│  • health_routes.py                                     │
│  • quiz_routes.py                                       │
│  • auth_routes.py                                       │
│  • user_activity_routes.py                             │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   Controllers Layer                      │
│  (Business Logic, Data Processing)                      │
│  • quiz_controller.py                                   │
│  • auth_controller.py                                   │
│  • user_activity_controller.py                         │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     Models Layer                         │
│  (Data Access, Database Operations)                     │
│  • DBController, QuizController                         │
│  • UserController, QuestionsController                  │
│  • TopTensController                                    │
└─────────────────────────────────────────────────────────┘
```

## 📋 Component Responsibilities

### **server.py** - Application Entry Point
- Initialize Flask app
- Setup database connections
- Register route blueprints
- Configure middleware (logging, metrics)
- **No business logic!**

### **Routes** (`routes/`) - HTTP Layer
- Define API endpoints
- Handle HTTP requests/responses
- Parse and validate request data
- Call controller methods
- Format responses
- **No business logic!**

### **Controllers** (`controllers/`) - Business Logic
- Implement business rules
- Process data
- Coordinate between routes and models
- Reusable across different routes
- **No HTTP knowledge!**

### **Models** (`models/`) - Database Layer
- Database connection management
- CRUD operations
- Data validation at DB level
- MongoDB-specific logic
- **No business logic!**

### **Utils** (`utils/`) - Shared Utilities
- Configuration management
- AI/OpenAI integration
- Quiz data utilities
- Input validation helpers
- **Reusable across all layers!**

## 🔄 Request Flow Example

```
HTTP POST /api/question/generate
         ↓
routes/quiz_routes.py: generate_question()
    ├─ Validate request data
    ├─ Extract parameters
    └─ Call controller ↓

controllers/quiz_controller.py: generate_quiz_question()
    ├─ Get random keyword (via utils)
    ├─ Get style modifier (via utils)
    ├─ Call AI service (via utils)
    └─ Return question data ↓

utils/quiz_utils.py
    └─ Access models/quiz_controller ↓

models/quiz_controller.py
    └─ MongoDB operations ↓

HTTP Response 200 OK
```

## ✅ Benefits of This Structure

### 1. **Separation of Concerns**
- Clear boundaries between layers
- Easy to understand what each file does
- Changes in one layer don't affect others

### 2. **Matches Industry Standards**
- Similar to Bomt-React and other professional projects
- Familiar to developers from other frameworks
- Easy onboarding for new team members

### 3. **Testability**
- Controllers can be unit tested without HTTP mocking
- Models can be tested independently
- Clear interfaces between layers

### 4. **Maintainability**
- New features are easy to add
- Logic changes don't affect routing
- Clear file organization

### 5. **Scalability**
- Easy to add new endpoints
- Can split into microservices later
- Clear API boundaries

## 🚀 Running the Application

### Local Development
```bash
cd server
python server.py
```

### With Docker
```bash
docker build -t quiz-backend -f ci/app-dockerfile/Dockerfile .
docker run -p 5000:5000 quiz-backend
```

### With Gunicorn (Production)
```bash
cd server
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 server:app
```

## 📚 API Endpoints

All existing endpoints work the same:

- `GET /api/health` - Health check
- `GET /api/categories` - Get quiz categories
- `GET /api/subjects` - Get subjects
- `POST /api/question/generate` - Generate question
- `POST /api/answer/evaluate` - Evaluate answer
- `GET /api/auth/login` - OAuth login
- `GET /api/auth/callback` - OAuth callback
- `POST /api/answers` - Save answer
- `GET /api/leaderboard` - Get leaderboard
- `POST /api/leaderboard/update` - Update leaderboard

## 📝 Adding New Features

### Example: Add a new endpoint

1. **Create Model Method** (if needed) in `models/`:
   ```python
   def get_quiz_by_id(self, quiz_id: str):
       # Database operations
       return quiz
   ```

2. **Create Controller Method** in `controllers/`:
   ```python
   @staticmethod
   def get_quiz_stats(category: str) -> Dict[str, Any]:
       # Business logic here
       return stats
   ```

3. **Create Route** in `routes/`:
   ```python
   @quiz_bp.route("/quiz/stats")
   def get_stats():
       category = request.args.get("category")
       stats = QuizController.get_quiz_stats(category)
       return jsonify(stats)
   ```

## 🎯 Best Practices

1. **Models should NOT:**
   - Contain business logic
   - Know about HTTP requests
   - Import from controllers or routes

2. **Controllers should NOT:**
   - Import Flask request/response objects
   - Return Flask responses (return data only)
   - Access database directly (use models)

3. **Routes should NOT:**
   - Contain business logic
   - Access database directly
   - Perform complex calculations

4. **Keep it DRY:**
   - Shared validation in utils/validation.py
   - Shared utilities in utils/
   - Reusable logic in controllers

## 🔍 Environment Variables

Required environment variables:
- `MONGODB_HOST` - MongoDB hostname
- `MONGODB_PORT` - MongoDB port (default: 27017)
- `MONGODB_USERNAME` - MongoDB username (optional)
- `MONGODB_PASSWORD` - MongoDB password (optional)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth secret
- `OPENAI_API_KEY` - OpenAI API key
- `JWT_SECRET_KEY` - JWT signing key

## 🧪 Testing

Run tests:
```bash
cd server
pytest tests/
```

Run with coverage:
```bash
pytest --cov=. tests/
```

---

**Structure inspired by:** [Bomt-React](https://github.com/L33Tify/Bomt-React)

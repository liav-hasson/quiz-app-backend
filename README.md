# Quiz App Backend

REST API for the DevOps Quiz application. Generates quiz questions using OpenAI and evaluates user answers.

## Features

- 🎯 **REST API** - Stateless JSON API for React frontend
- 🤖 **AI-Powered** - Uses OpenAI GPT-4o-mini for question generation and evaluation
- 🔒 **Secure** - AWS SSM Parameter Store integration for API keys
- 📊 **Quiz Database** - JSON-based knowledge base with multiple categories and subjects
- 🐳 **Containerized** - Docker and docker-compose ready
- ✅ **Tested** - Unit and integration tests with pytest

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (or AWS SSM Parameter Store access)

### Local Development

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r src/requirements.txt
   ```

4. **Set environment variables:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   export FLASK_DEBUG=true
   ```

5. **Run the application:**
   ```bash
   cd src/python
   python main.py
   ```

   The API will be available at `http://localhost:5000`

### Docker Development

1. **Using docker-compose:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   docker-compose up
   ```

2. **Build and run manually:**
   ```bash
   docker build -t quiz-backend .
   docker run -p 5000:5000 -e OPENAI_API_KEY="your-key" quiz-backend
   ```

## API Endpoints

### Health Check
```http
GET /api/health
```
Returns API health status.

**Response:**
```json
{"status": "ok"}
```

### Get Categories
```http
GET /api/categories
```
Returns all available quiz categories.

**Response:**
```json
{
  "categories": ["Containers", "Kubernetes", "CI/CD", ...]
}
```

### Get Subjects
```http
GET /api/subjects?category=Containers
```
Returns subjects for a specific category.

**Parameters:**
- `category` (string, required) - The category name

**Response:**
```json
{
  "subjects": ["Basics", "Docker Commands", "Docker Architecture"]
}
```

### Generate Question
```http
POST /api/question/generate
```
Generates a quiz question based on category, subject, and difficulty.

**Request Body:**
```json
{
  "category": "Containers",
  "subject": "Basics",
  "difficulty": 1
}
```

**Parameters:**
- `category` (string, required) - Quiz category
- `subject` (string, required) - Quiz subject within category
- `difficulty` (integer, required) - Difficulty level (1=basic, 2=intermediate, 3=advanced)

**Response:**
```json
{
  "question": "What is a container?",
  "keyword": "Container",
  "category": "Containers",
  "subject": "Basics",
  "difficulty": 1
}
```

### Evaluate Answer
```http
POST /api/answer/evaluate
```
Evaluates a user's answer and provides feedback.

**Request Body:**
```json
{
  "question": "What is a container?",
  "answer": "A lightweight, standalone package that includes everything needed to run software",
  "difficulty": 1
}
```

**Parameters:**
- `question` (string, required) - The question being answered
- `answer` (string, required) - User's answer
- `difficulty` (integer, required) - Question difficulty level (1-3)

**Response:**
```json
{
  "feedback": "Your score: 9/10\nExcellent answer! You've captured the key concepts..."
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_DEBUG` | `false` | Enable debug mode (true/false) |
| `FLASK_HOST` | `0.0.0.0` | Host to bind to |
| `FLASK_PORT` | `5000` | Port to listen on |
| `OPENAI_API_KEY` | - | OpenAI API key (required if not using SSM) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `SSM_PARAMETER_NAME` | `/devops-quiz/openai-api-key` | AWS SSM parameter name for API key |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

### AWS SSM Integration

The backend supports retrieving the OpenAI API key from AWS Systems Manager Parameter Store:

1. Store your key in SSM:
   ```bash
   aws ssm put-parameter \
     --name /devops-quiz/openai-api-key \
     --value "your-api-key" \
     --type SecureString
   ```

2. Ensure your IAM role/user has `ssm:GetParameter` permission

3. Run without `OPENAI_API_KEY` env var - it will automatically fetch from SSM

## Testing

Run the test suite:

```bash
cd src/python
pytest
```

Run with coverage:

```bash
pytest --cov=. --cov-report=html
```

## Project Structure

```
backend/
├── src/
│   ├── db/
│   │   └── db.json              # Quiz questions database
│   ├── python/
│   │   ├── main.py              # Flask API application
│   │   ├── config.py            # Configuration module
│   │   ├── validation.py        # Input validation utilities
│   │   ├── quiz_utils.py        # Quiz database utilities
│   │   ├── ai_utils.py          # OpenAI integration
│   │   ├── test_*.py            # Test files
│   │   └── ...
│   └── requirements.txt         # Python dependencies
├── Dockerfile                   # Container image definition
├── docker-compose.yml           # Local development setup
├── nginx.conf                   # Nginx configuration for production
└── README.md                    # This file
```

## Production Deployment

### Kubernetes

The backend is designed to run in Kubernetes with:
- **Backend pod**: Flask API with gunicorn
- **Nginx pod**: Serves React frontend and proxies `/api/*` to backend

See the `gitops` repository for Kubernetes manifests and Helm charts.

### Nginx Configuration

The included `nginx.conf` provides:
- Static file serving for React frontend
- API proxy to backend service
- Compression and caching
- Security headers

Deploy in Kubernetes:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
data:
  default.conf: |
    # Contents of nginx.conf
```

## Development

### Adding New Quiz Categories

1. Edit `src/db/db.json`
2. Add new category with subjects and keywords:
   ```json
   "NewCategory": {
     "SubjectName": {
       "keywords": ["keyword1", "keyword2", ...]
     }
   }
   ```

### Code Style

- Follow PEP 8
- Use docstrings for all functions
- Type hints where appropriate
- Keep functions small and focused

### Contributing

1. Create a feature branch
2. Make changes with tests
3. Ensure all tests pass
4. Submit pull request

## License

MIT License - See LICENSE file for details

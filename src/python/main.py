"""
Quiz App main.py

This application provides:
- Google OAuth 2.0 authentication with JWT token issuance
- AI-generated quiz questions using OpenAI
- Answer evaluation and scoring
- User statistics and leaderboard tracking
- Prometheus metrics for monitoring

Architecture:
- Flask for REST API
- MongoDB for data persistence (4 collections: users, quiz_data, questions, top_ten)
- OpenAI for question generation and answer evaluation
- Google OAuth for authentication
"""

# Standard library imports
from flask import Flask, request, jsonify, g
import logging
import time
import os
import sys
from typing import Optional
from datetime import datetime, timedelta, timezone

# Third-party imports
from prometheus_flask_exporter import PrometheusMetrics
import jwt

# Local application imports (absolute imports work with PYTHONPATH set in Dockerfile)
from python.config import Config
from python.validation import validate_difficulty, validate_required_fields
from python.quiz_utils import (
    get_categories, 
    get_subjects, 
    get_random_keyword, 
    get_random_style_modifier
)
from python.ai_utils import generate_question, evaluate_answer
from db import (
    DBController, 
    QuizController, 
    DataMigrator, 
    UserController, 
    QuestionsController, 
    TopTenController
)


# Logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Flask app initialization
app = Flask(__name__)


# GLOBAL CONTROLLERS
# These are initialized in initialize_database() before the app starts
db_controller: Optional[DBController] = None            # MongoDB connection
quiz_controller: Optional[QuizController] = None        # Quiz data (topics, keywords)
user_controller: Optional[UserController] = None        # User management
questions_controller: Optional[QuestionsController] = None  # Answer tracking
toptens_controller: Optional[TopTenController] = None   # Leaderboard
oauth = None  # type: ignore                            # Google OAuth client


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def initialize_database():
    """
    Initialize database connection and verify quiz data exists.
    
    This function:
    1. Establishes MongoDB connection
    2. Initializes all database controllers
    3. Sets up Google OAuth client
    4. Verifies quiz data exists in MongoDB
    
    Database Initialization:
    - In Kubernetes: Data is initialized by mongodb-init Job (ArgoCD PostSync hook)
    - In Docker Compose/Local: Can auto-migrate from local db.json file
    
    Returns:
        bool: True if initialization successful, False otherwise
    
    Environment Variables:
        GOOGLE_CLIENT_ID: Google OAuth client ID
        GOOGLE_CLIENT_SECRET: Google OAuth client secret
        AUTO_MIGRATE_DB: Enable auto-migration from local db.json (default: 'true')
                        Set to 'false' in Kubernetes (mongodb-init Job handles data)
    """
    global db_controller, quiz_controller
    global user_controller, questions_controller, toptens_controller, oauth

    try:
        # Step 1: Connect to MongoDB
        print("Connecting to MongoDB...")
        db_controller = DBController()

        if not db_controller.connect():
            print("ERROR: Failed to connect to MongoDB at localhost:27017")
            print("Please ensure MongoDB is running: mongod --dbpath /path/to/your/data")
            return False

        # Step 2: Initialize all database controllers
        quiz_controller = QuizController(db_controller)
        user_controller = UserController(db_controller)
        questions_controller = QuestionsController(db_controller)
        toptens_controller = TopTenController(db_controller)

        # Step 3: Initialize Google OAuth client
        # Note: Lazy import allows tests to run without authlib installed
        try:
            from authlib.integrations.flask_client import OAuth

            oauth = OAuth()
            oauth.init_app(app)
            oauth.register(
                name="google",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
        except Exception as e:
            logger.error('oauth_initialization_failed %s', str(e), exc_info=True)
            raise RuntimeError(f"Failed to initialize OAuth: {e}")

        # Step 4: Verify quiz data exists in MongoDB
        topics = quiz_controller.get_all_topics()

        if not topics:
            # No quiz data found - check if auto-migration is enabled
            auto_migrate = os.getenv('AUTO_MIGRATE_DB', 'true').lower() == 'true'
            
            if auto_migrate:
                # Local development mode: migrate from local db.json file
                print("WARNING: No quiz data found in MongoDB!")
                print("Attempting to migrate data from local db.json...")

                json_path = os.path.join(os.path.dirname(__file__), "..", "db", "db.json")
                if os.path.exists(json_path):
                    migrator = DataMigrator(db_controller, quiz_controller)
                    if migrator.migrate_from_json_file(json_path):
                        print("✅ Data migration successful!")
                        topics = quiz_controller.get_all_topics()
                        print(f"Available topics: {topics}")
                    else:
                        print("ERROR: Data migration failed!")
                        return False
                else:
                    print(f"ERROR: db.json not found at {json_path}")
                    return False
            else:
                # Kubernetes production mode: mongodb-init Job should have initialized the database
                print("ERROR: No quiz data found in MongoDB!")
                print("AUTO_MIGRATE_DB is disabled. Expected mongodb-init Job to initialize database.")
                print("")
                print("Troubleshooting:")
                print("  1. Check mongodb-init Job status: kubectl get jobs -n mongodb")
                print("  2. View Job logs: kubectl logs -n mongodb job/mongodb-init-<pod>")
                print("  3. Verify ArgoCD sync: argocd app sync mongodb-init")
                print("  4. Ensure mongodb-init runs AFTER MongoDB is healthy (PostSync hook)")
                return False
        else:
            print(f"✅ Connected to MongoDB successfully!")
            print(f"Available topics: {topics}")

        return True

    except Exception as e:
        print(f"ERROR: Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# PROMETHEUS METRICS
# ============================================================================
# Automatically creates /metrics endpoint and tracks HTTP request metrics

metrics = PrometheusMetrics(app)
metrics.info("quiz_app_info", "Quiz Application Info", version="1.0.0")


# ============================================================================
# REQUEST LOGGING & MIDDLEWARE
# ============================================================================

@app.before_request
def before_request():
    """
    Log request start and track timing.
    
    Stores start time in Flask's g object for duration calculation.
    Logs: HTTP method, path, and remote IP address.
    """
    g.start_time = time.time()
    logger.info(
        "request_started method=%s path=%s remote_addr=%s",
        request.method,
        request.path,
        request.remote_addr,
    )


@app.after_request
def after_request(response):
    """
    Log request completion with duration.
    
    Calculates request duration and logs completion status.
    Logs: HTTP method, path, status code, and duration in milliseconds.
    
    Args:
        response: Flask response object
        
    Returns:
        response: Unmodified response object
    """
    if hasattr(g, "start_time"):
        duration = time.time() - g.start_time
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            duration * 1000,
        )
    return response


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def error_response(message, code=400):
    """
    Create standardized error response.
    
    Args:
        message (str): Error message to return to client
        code (int): HTTP status code (default: 400)
        
    Returns:
        tuple: (JSON response, status code)
    """
    return jsonify({"error": message}), code


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route("/api/health")
def health():
    """
    Health check endpoint.
    
    Used by Docker healthcheck and Kubernetes probes.
    Returns app status and database connection status.
    
    Returns:
        JSON: {"status": "ok", "database": "connected|disconnected"}
    """
    logger.debug("health_check_called")
    db_status = (
        "connected"
        if db_controller and db_controller.db is not None
        else "disconnected"
    )
    return jsonify({"status": "ok", "database": db_status})


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.route('/api/auth/login')
def auth_login():
    """
    Initiate Google OAuth 2.0 login flow.
    
    Redirects user to Google's OAuth consent screen.
    After user approves, Google redirects back to /api/auth/callback.
    
    Returns:
        Redirect: Redirect to Google OAuth consent page
        
    Environment Variables:
        GOOGLE_CLIENT_ID: Google OAuth client ID
        GOOGLE_CLIENT_SECRET: Google OAuth client secret
    """
    # Build redirect URI dynamically based on request origin
    redirect_uri = request.url_root.rstrip('/') + '/api/auth/callback'
    
    try:
        return oauth.google.authorize_redirect(redirect_uri)  # type: ignore
    except Exception as e:
        logger.error('oauth_login_failed %s', str(e), exc_info=True)
        return error_response('OAuth login failed', 500)


@app.route('/api/auth/callback')
def auth_callback():
    """
    Handle Google OAuth callback and issue JWT token.
    
    This endpoint:
    1. Receives authorization code from Google
    2. Exchanges code for access token
    3. Retrieves user info from Google
    4. Creates or updates user in database
    5. Issues JWT token for the user
    
    Returns:
        JSON: {
            "token": "<jwt_token>",
            "user": {
                "_id": "<user_id>",
                "email": "<email>",
                "name": "<name>",
                "profile_picture": "<url>"
            }
        }
        
    Environment Variables:
        JWT_SECRET: Secret key for signing JWTs (default: 'devsecret')
        JWT_EXP_DAYS: JWT expiration in days (default: 7)
    """
    try:
        # Step 1: Exchange authorization code for access token
        token = oauth.google.authorize_access_token()  # type: ignore
        
        # Step 2: Get user info from Google (try OIDC ID token first, fallback to userinfo endpoint)
        try:
            user_info = oauth.google.parse_id_token(token)  # type: ignore
        except Exception:
            resp = oauth.google.get('userinfo')  # type: ignore
            user_info = resp.json()

        # Step 3: Extract user information
        google_id = user_info.get('sub')        # Google's unique user ID
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')

        if not google_id or not email:
            return error_response('Failed to obtain user info from provider', 400)

        # Step 4: Create or update user in database
        try:
            assert user_controller is not None, "UserController not initialized"
            user = user_controller.create_or_update_google_user(
                google_id=google_id, 
                email=email, 
                name=name, 
                picture=picture
            )

            # Step 5: Issue JWT token
            jwt_secret = os.getenv('JWT_SECRET', 'devsecret')
            jwt_exp_days = int(os.getenv('JWT_EXP_DAYS', '7'))
            now = datetime.now(timezone.utc)
            
            payload = {
                'sub': user.get('_id'),      # Subject: user ID
                'email': user.get('email'),
                'name': user.get('name'),
                'exp': now + timedelta(days=jwt_exp_days),  # Expiration time
                'iat': now,                  # Issued at time
            }
            token_jwt = jwt.encode(payload, jwt_secret, algorithm='HS256')

            return jsonify({'token': token_jwt, 'user': user})
            
        except Exception as e:
            logger.error('user_create_or_update_failed %s', str(e), exc_info=True)
            return error_response('Failed to create or update user', 500)

    except Exception as e:
        logger.error('oauth_callback_failed %s', str(e), exc_info=True)
        return error_response('OAuth callback failed', 500)


# ============================================================================
# QUIZ METADATA ENDPOINTS
# ============================================================================

@app.route("/api/categories")
def api_categories():
    """
    Get all available quiz categories.
    
    Returns all top-level categories (e.g., Containers, CI/CD, Kubernetes).
    Used by frontend to populate category dropdown.
    
    Returns:
        JSON: {"categories": ["Containers", "CI/CD", ...]}
    """
    try:
        categories = get_categories()
        logger.info("categories_fetched count=%d", len(categories))
        return jsonify({"categories": categories})
    except Exception as e:
        logger.error("categories_fetch_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to get categories: {str(e)}", 500)


@app.route("/api/subjects")
def api_subjects():
    """
    Get subjects (subtopics) for a specific category.
    
    Query Parameters:
        category (str): Category name (e.g., "Containers")
        
    Returns:
        JSON: {"subjects": ["Docker", "Podman", ...]}
        
    Example:
        GET /api/subjects?category=Containers
    """
    category = request.args.get("category")
    if not category:
        logger.warning("subjects_request_missing_category")
        return error_response("category parameter required")

    try:
        subjects = get_subjects(category)
        logger.info("subjects_fetched category=%s count=%d", category, len(subjects))
        return jsonify({"subjects": subjects})
    except Exception as e:
        logger.error(
            "subjects_fetch_failed category=%s error=%s",
            category,
            str(e),
            exc_info=True,
        )
        return error_response(f"Failed to get subjects: {str(e)}", 500)


# ============================================================================
# QUESTION GENERATION & EVALUATION ENDPOINTS
# ============================================================================

@app.route("/api/question/generate", methods=["POST"])
def api_generate_question():
    """    
    Uses OpenAI to generate a contextual DevOps question based on:
    - Category and subject (e.g., Containers -> Docker)
    - Random keyword from the subject
    - Difficulty level (1=Easy, 2=Medium, 3=Hard)
    - Random style modifier (concept, use case, troubleshooting, comparison)
    
    Request Body:
        {
            "category": "Containers",
            "subject": "Docker",
            "difficulty": 1
        }
        
    Returns:
        JSON: {
            "question": "What is the purpose of...",
            "keyword": "dockerfile",
            "category": "Containers",
            "subject": "Docker",
            "difficulty": 1
        }
    """
    data = request.get_json()

    # Validate input
    try:
        validate_required_fields(data, ["category", "subject", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("generate_question_validation_failed error=%s", str(e))
        return error_response(str(e))

    logger.info(
        "generating_question category=%s subject=%s difficulty=%d",
        data["category"],
        data["subject"],
        difficulty,
    )

    try:
        # Select random keyword to focus the question
        keyword = get_random_keyword(data["category"], data["subject"])
        if not keyword:
            logger.warning(
                "no_keywords_found category=%s subject=%s",
                data["category"],
                data["subject"],
            )
            return error_response("No keywords found", 404)

        # Select random style modifier (e.g., "use case scenario", "troubleshooting")
        style_modifier = get_random_style_modifier(data["category"], data["subject"])
        
        # Generate question using OpenAI
        question = generate_question(
            data["category"], data["subject"], keyword, difficulty, style_modifier
        )
        
        logger.info(
            "question_generated category=%s subject=%s difficulty=%d keyword=%s style_modifier=%s",
            data["category"],
            data["subject"],
            difficulty,
            keyword,
            style_modifier,
        )

        return jsonify({
            "question": question,
            "keyword": keyword,
            "category": data["category"],
            "subject": data["subject"],
            "difficulty": difficulty,
        })
        
    except Exception as e:
        logger.error(
            "question_generation_failed category=%s subject=%s error=%s",
            data["category"],
            data["subject"],
            str(e),
            exc_info=True,
        )
        raise


@app.route("/api/answer/evaluate", methods=["POST"])
def api_evaluate_answer():
    """
    Evaluate a user's answer using AI.
    
    Uses OpenAI to:
    - Score the answer (1-10)
    - Provide constructive feedback
    - Correct mistakes and suggest study topics
    
    Scoring is difficulty-adjusted:
    - Easy (1): Expects 3-5 sentence answers
    - Medium (2): More detailed explanations required
    - Hard (3): Deep technical understanding expected
    
    Request Body:
        {
            "question": "What is Docker?",
            "answer": "Docker is a containerization platform...",
            "difficulty": 1
        }
        
    Returns:
        JSON: {
            "feedback": "Your score: 8/10\nfeedback: Good answer! You correctly identified..."
        }
    """
    data = request.get_json()

    # Validate input
    try:
        validate_required_fields(data, ["question", "answer", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("evaluate_answer_validation_failed error=%s", str(e))
        return error_response(str(e))

    logger.info(
        "evaluating_answer difficulty=%d answer_length=%d",
        difficulty,
        len(data["answer"]),
    )

    try:
        # Use OpenAI to evaluate the answer
        feedback = evaluate_answer(data["question"], data["answer"], difficulty)
        
        logger.info(
            "answer_evaluated difficulty=%d feedback_length=%d",
            difficulty,
            len(feedback),
        )
        return jsonify({"feedback": feedback})
        
    except Exception as e:
        logger.error("answer_evaluation_failed error=%s", str(e), exc_info=True)
        raise


# ============================================================================
# USER STATISTICS & TRACKING ENDPOINTS
# ============================================================================

@app.route("/api/answers", methods=["POST"])
def api_save_answer():
    """
    Save a user's answer for statistics tracking.
    
    Records:
    - Question and answer text
    - Score received
    - Category and subject
    - Timestamp
    
    Also updates user statistics:
    - Total experience points (sum of all scores)
    - Total questions answered
    
    Request Body:
        {
            "user_id": "507f1f77bcf86cd799439011",
            "username": "john_doe",
            "question": "What is Docker?",
            "answer": "Docker is...",
            "score": 8,
            "difficulty": 1,
            "category": "Containers",
            "subject": "Docker",
            "keyword": "docker",
            "is_correct": true
        }
        
    Returns:
        JSON: {"answer_id": "507f1f77bcf86cd799439012"}
        Status: 201 Created
    """
    data = request.get_json()

    # Validate required fields
    try:
        validate_required_fields(
            data, 
            ["user_id", "username", "question", "answer", "difficulty", "category", "subject"]
        )
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("save_answer_validation_failed error=%s", str(e))
        return error_response(str(e))

    try:
        # Step 1: Save the answer record to questions collection
        assert questions_controller is not None, "QuestionsController not initialized"
        answer_id = questions_controller.add_question(
            user_id=data["user_id"],
            username=data["username"],
            question_text=data["question"],
            keyword=data.get("keyword", ""),
            category=data["category"],
            subject=data["subject"],
            difficulty=difficulty,
            ai_generated=True,
            extra={
                "user_answer": data["answer"],
                "is_correct": data.get("is_correct"),
                "score": data.get("score"),
            },
        )
        
        # Step 2: Update user's experience points and question count
        score_earned = data.get("score", 0)
        assert user_controller is not None, "UserController not initialized"
        user_controller.add_experience(data["username"], score_earned)
        
        logger.info(
            "answer_saved answer_id=%s user_id=%s category=%s score=%s", 
            answer_id, data["user_id"], data["category"], score_earned
        )
        return jsonify({"answer_id": answer_id}), 201
        
    except Exception as e:
        logger.error("answer_save_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to save answer: {str(e)}", 500)


# ============================================================================
# LEADERBOARD ENDPOINTS
# ============================================================================

@app.route("/api/leaderboard", methods=["GET"])
def api_get_leaderboard():
    """
    Get top 10 users by average score.
    
    The leaderboard ranks users by their average score across all questions.
    Score calculation: total_experience / questions_answered
    
    Returns:
        JSON: {
            "leaderboard": [
                {
                    "username": "john_doe",
                    "score": 8.5,
                    "meta": {"exp": 85, "count": 10}
                },
                ...
            ],
            "count": 10
        }
    """
    try:
        assert toptens_controller is not None, "TopTenController not initialized"
        top_ten = toptens_controller.get_top_ten()
        logger.info("leaderboard_fetched count=%d", len(top_ten))
        return jsonify({"leaderboard": top_ten, "count": len(top_ten)})
    except Exception as e:
        logger.error("leaderboard_fetch_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to fetch leaderboard: {str(e)}", 500)


@app.route("/api/leaderboard/update", methods=["POST"])
def api_update_leaderboard():
    """
    Update a user's leaderboard entry with current stats.
    
    Calculates user's average score from their stats:
    - Gets total experience points
    - Gets total questions answered
    - Computes average: exp / count
    - Updates leaderboard entry
    
    The leaderboard automatically maintains top 10 users only.
    
    Request Body:
        {
            "user_id": "507f1f77bcf86cd799439011",
            "username": "john_doe"
        }
        
    Returns:
        JSON: {
            "status": "updated",
            "avg_score": 8.5
        }
        Status: 201 Created
    """
    data = request.get_json()

    # Validate input
    try:
        validate_required_fields(data, ["user_id", "username"])
    except ValueError as e:
        logger.warning("leaderboard_update_validation_failed error=%s", str(e))
        return error_response(str(e))

    try:
        # Step 1: Fetch user's current statistics
        assert user_controller is not None, "UserController not initialized"
        user = user_controller.get_user_by_username(data["username"])
        if not user:
            logger.warning("user_not_found username=%s", data["username"])
            return error_response("User not found", 404)
        
        exp = user.get("experience", 0)           # Total experience points
        count = user.get("questions_count", 1)    # Total questions answered
        
        # Step 2: Calculate average score
        avg_score = exp / count if count > 0 else 0
        
        # Step 3: Update leaderboard
        assert toptens_controller is not None, "TopTenController not initialized"
        toptens_controller.add_or_update_entry(
            username=data["username"],
            score=avg_score,
            meta={"exp": exp, "count": count},
        )
        
        logger.info(
            "leaderboard_entry_updated username=%s avg_score=%.2f exp=%d count=%d", 
            data["username"], avg_score, exp, count
        )
        return jsonify({"status": "updated", "avg_score": avg_score}), 201
        
    except Exception as e:
        logger.error("leaderboard_update_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to update leaderboard: {str(e)}", 500)


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Development server entry point.
    
    In production, the app is run with gunicorn:
        gunicorn --bind 0.0.0.0:5000 --workers 2 python.main:app
    
    This block is only used for local development/testing.
    """
    
    # Initialize database connection before starting the app
    if not initialize_database():
        print("\n" + "=" * 60)
        print("FATAL ERROR: Cannot start Flask app without database!")
        print("Please fix the database connection and try again.")
        print("=" * 60)
        sys.exit(1)

    # Start Flask development server
    print("\n" + "=" * 60)
    print(f"Starting Flask app on {Config.HOST}:{Config.PORT}")
    print("=" * 60 + "\n")

    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)

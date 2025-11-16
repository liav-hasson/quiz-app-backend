"""Quiz app REST API."""
from flask import Flask, request, jsonify, g
import logging
import time
from typing import Optional
from prometheus_flask_exporter import PrometheusMetrics
from config import Config
from validation import validate_difficulty, validate_required_fields
from quiz_utils import get_categories, get_subjects, get_random_keyword, get_random_style_modifier
from ai_utils import generate_question, evaluate_answer
import sys
import os

# Add db path for controller access
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
sys.path.insert(0, db_path)

from db import DBController, QuizController, DataMigrator, UserController, QuestionsController, TopTenController
from authlib.integrations.flask_client import OAuth
import jwt 

from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database controllers
db_controller: Optional[DBController] = None
quiz_controller: Optional[QuizController] = None
user_controller: Optional[UserController] = None
questions_controller: Optional[QuestionsController] = None
toptens_controller: Optional[TopTenController] = None
oauth: OAuth = None  # type: ignore


def initialize_database():
    """Initialize database connection and verify data exists"""
    global db_controller, quiz_controller
    global user_controller, questions_controller, toptens_controller, oauth

    try:
        print("Connecting to MongoDB...")
        db_controller = DBController()

        if not db_controller.connect():
            print("ERROR: Failed to connect to MongoDB at localhost:27017")
            print(
                "Please ensure MongoDB is running: mongod --dbpath /path/to/your/data"
            )
            return False

        quiz_controller = QuizController(db_controller)
        user_controller = UserController(db_controller)
        questions_controller = QuestionsController(db_controller)
        toptens_controller = TopTenController(db_controller)

        # Initialize OAuth client
        try:
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

        # Check if data exists
        topics = quiz_controller.get_all_topics()

        if not topics:
            # Check if auto-migration is enabled (default: true for backward compatibility)
            auto_migrate = os.getenv('AUTO_MIGRATE_DB', 'true').lower() == 'true'
            
            if auto_migrate:
                print("WARNING: No quiz data found in MongoDB!")
                print("Attempting to migrate data from db.json...")

                # Try to migrate data
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
                print("ERROR: No quiz data found in MongoDB!")
                print("AUTO_MIGRATE_DB is disabled. Database must be initialized using mongodb-init Job.")
                print("If running in Kubernetes, ensure the mongodb-init Job has completed successfully.")
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


# Initialize Prometheus metrics
# This automatically creates /metrics endpoint and tracks HTTP metrics
metrics = PrometheusMetrics(app)

# Add custom info metric
metrics.info("quiz_app_info", "Quiz Application Info", version="1.0.0")


@app.before_request
def before_request():
    """Log request start and track timing."""
    g.start_time = time.time()
    logger.info(
        "request_started method=%s path=%s remote_addr=%s",
        request.method,
        request.path,
        request.remote_addr,
    )


@app.after_request
def after_request(response):
    """Log request completion with duration."""
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


# Error message template
def error_response(message, code=400):
    """Return error response."""
    return jsonify({"error": message}), code


# Health check route
@app.route("/api/health")
def health():
    """Health check."""
    logger.debug("health_check_called")
    db_status = (
        "connected"
        if db_controller and db_controller.db is not None
        else "disconnected"
    )
    return jsonify({"status": "ok", "database": db_status})


@app.route('/api/auth/login')
def auth_login():
    """Start Google OAuth login flow."""
    # Build redirect URI dynamically
    redirect_uri = request.url_root.rstrip('/') + '/api/auth/callback'
    try:
        return oauth.google.authorize_redirect(redirect_uri)  # type: ignore
    except Exception as e:
        logger.error('oauth_login_failed %s', str(e), exc_info=True)
        return error_response('OAuth login failed', 500)


@app.route('/api/auth/callback')
def auth_callback():
    """Handle Google OAuth callback and create/update user."""
    try:
        token = oauth.google.authorize_access_token()  # type: ignore
        # Try to parse ID token (OIDC) or fetch userinfo
        try:
            user_info = oauth.google.parse_id_token(token)  # type: ignore
        except Exception:
            resp = oauth.google.get('userinfo')  # type: ignore
            user_info = resp.json()

        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')

        if not google_id or not email:
            return error_response('Failed to obtain user info from provider', 400)

        # Create or update user in DB
        try:
            assert user_controller is not None, "UserController not initialized"
            user = user_controller.create_or_update_google_user(google_id=google_id, email=email, name=name, picture=picture)

            # Issue JWT for the user
            jwt_secret = os.getenv('JWT_SECRET', 'devsecret')
            jwt_exp_days = int(os.getenv('JWT_EXP_DAYS', '7'))
            now = datetime.now(timezone.utc)
            payload = {
                'sub': user.get('_id'),
                'email': user.get('email'),
                'name': user.get('name'),
                'exp': now + timedelta(days=jwt_exp_days),
                'iat': now,
            }
            token_jwt = jwt.encode(payload, jwt_secret, algorithm='HS256')

            return jsonify({'token': token_jwt, 'user': user})
        except Exception as e:
            logger.error('user_create_or_update_failed %s', str(e), exc_info=True)
            return error_response('Failed to create or update user', 500)

    except Exception as e:
        logger.error('oauth_callback_failed %s', str(e), exc_info=True)
        return error_response('OAuth callback failed', 500)


# Returns all categories
@app.route("/api/categories")
def api_categories():
    """Get all categories."""
    try:
        categories = get_categories()
        logger.info("categories_fetched count=%d", len(categories))
        return jsonify({"categories": categories})
    except Exception as e:
        logger.error("categories_fetch_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to get categories: {str(e)}", 500)


@app.route("/api/subjects")
def api_subjects():
    """Get subjects for category."""
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


@app.route("/api/question/generate", methods=["POST"])
def api_generate_question():
    """Generate a question."""
    data = request.get_json()

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
        keyword = get_random_keyword(data["category"], data["subject"])
        if not keyword:
            logger.warning(
                "no_keywords_found category=%s subject=%s",
                data["category"],
                data["subject"],
                data["difficulty"],
            )
            return error_response("No keywords found", 404)

        # Get random style modifier for this category/subject
        style_modifier = get_random_style_modifier(data["category"], data["subject"])
        
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

        return jsonify(
            {
                "question": question,
                "keyword": keyword,
                "category": data["category"],
                "subject": data["subject"],
                "difficulty": difficulty,
            }
        )
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
    """Evaluate an answer."""
    data = request.get_json()

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


# Answer tracking endpoint
@app.route("/api/answers", methods=["POST"])
def api_save_answer():
    """Save a user's answer to a question for statistics tracking."""
    data = request.get_json()

    try:
        validate_required_fields(data, ["user_id", "username", "question", "answer", "difficulty", "category", "subject"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("save_answer_validation_failed error=%s", str(e))
        return error_response(str(e))

    try:
        # Save the answer record
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
        
        # Update user's exp (accumulated score) and question count
        score_earned = data.get("score", 0)
        assert user_controller is not None, "UserController not initialized"
        user_controller.add_experience(data["username"], score_earned)
        
        logger.info("answer_saved answer_id=%s user_id=%s category=%s score=%s", answer_id, data["user_id"], data["category"], score_earned)
        return jsonify({"answer_id": answer_id}), 201
    except Exception as e:
        logger.error("answer_save_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to save answer: {str(e)}", 500)


# Leaderboard endpoints
@app.route("/api/leaderboard", methods=["GET"])
def api_get_leaderboard():
    """Get top 10 users by score (leaderboard)."""
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
    """Update leaderboard by calculating user's average score (exp/count)."""
    data = request.get_json()

    try:
        validate_required_fields(data, ["user_id", "username"])
    except ValueError as e:
        logger.warning("leaderboard_update_validation_failed error=%s", str(e))
        return error_response(str(e))

    try:
        # Get user's exp and question count
        assert user_controller is not None, "UserController not initialized"
        user = user_controller.get_user_by_username(data["username"])
        if not user:
            logger.warning("user_not_found username=%s", data["username"])
            return error_response("User not found", 404)
        
        exp = user.get("experience", 0)
        count = user.get("questions_count", 1)  # Default to 1 to avoid division by zero
        
        # Calculate average score: exp / count
        avg_score = exp / count if count > 0 else 0
        
        # Update leaderboard with calculated average
        assert toptens_controller is not None, "TopTenController not initialized"
        toptens_controller.add_or_update_entry(
            username=data["username"],
            score=avg_score,
            meta={"exp": exp, "count": count},
        )
        logger.info("leaderboard_entry_updated username=%s avg_score=%.2f exp=%d count=%d", data["username"], avg_score, exp, count)
        return jsonify({"status": "updated", "avg_score": avg_score}), 201
    except Exception as e:
        logger.error("leaderboard_update_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to update leaderboard: {str(e)}", 500)


if __name__ == "__main__":
    # Initialize database before starting the app
    if not initialize_database():
        print("\n" + "=" * 60)
        print("FATAL ERROR: Cannot start Flask app without database!")
        print("Please fix the database connection and try again.")
        print("=" * 60)
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"Starting Flask app on {Config.HOST}:{Config.PORT}")
    print("=" * 60 + "\n")

    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)

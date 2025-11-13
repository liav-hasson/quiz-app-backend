"""Quiz app REST API."""

from flask import Flask, request, jsonify, g
import logging
import time
from prometheus_flask_exporter import PrometheusMetrics
from config import Config
from validation import validate_difficulty, validate_required_fields
from quiz_utils import get_categories, get_subjects, get_random_keyword
from ai_utils import generate_question, evaluate_answer
import sys
import os

# Add db path for controller access
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
sys.path.insert(0, db_path)

from db.dbcontroller import DBController, QuizController, DataMigrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database controllers
db_controller = None
quiz_controller = None


def initialize_database():
    """Initialize database connection and verify data exists"""
    global db_controller, quiz_controller

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

        # Check if data exists
        topics = quiz_controller.get_all_topics()

        if not topics:
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
metrics.info('quiz_app_info', 'Quiz Application Info', version='1.0.0')


@app.before_request
def before_request():
    """Log request start and track timing."""
    g.start_time = time.time()
    logger.info(
        "request_started method=%s path=%s remote_addr=%s",
        request.method,
        request.path,
        request.remote_addr
    )


@app.after_request
def after_request(response):
    """Log request completion with duration."""
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            duration * 1000
        )
    return response

# Error message template
def error_response(message, code=400):
    """Return error response."""
    return jsonify({"error": message}), code


# Health check route
@app.route('/api/health')
def health():
    """Health check."""
    logger.debug("health_check_called")
    db_status = "connected" if db_controller and db_controller.db else "disconnected"
    return jsonify({'status': 'ok', 'database': db_status})


# Returns all categories
@app.route("/api/categories")
def api_categories():
    """Get all categories."""
    try:
        categories = get_categories()
        logger.info("categories_fetched count=%d", len(categories))
        return jsonify({'categories': categories})
    except Exception as e:
        logger.error("categories_fetch_failed error=%s", str(e), exc_info=True)
        return error_response(f"Failed to get categories: {str(e)}", 500)


@app.route("/api/subjects")
def api_subjects():
    """Get subjects for category."""
    category = request.args.get("category")
    if not category:
        logger.warning("subjects_request_missing_category")
        return error_response('category parameter required')
    
    try:
        subjects = get_subjects(category)
        logger.info("subjects_fetched category=%s count=%d", category, len(subjects))
        return jsonify({'subjects': subjects})
    except Exception as e:
        logger.error("subjects_fetch_failed category=%s error=%s", category, str(e), exc_info=True)
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
        data['category'],
        data['subject'],
        difficulty
    )
    
    try:
        keyword = get_random_keyword(data['category'], data['subject'])
        if not keyword:
            logger.warning(
                "no_keywords_found category=%s subject=%s",
                data['category'],
                data['subject']
            )
            return error_response('No keywords found', 404)
        
        question = generate_question(data['category'], keyword, difficulty)
        logger.info(
            "question_generated category=%s subject=%s difficulty=%d keyword=%s",
            data['category'],
            data['subject'],
            difficulty,
            keyword
        )
        
        return jsonify({
            'question': question,
            'keyword': keyword,
            'category': data['category'],
            'subject': data['subject'],
            'difficulty': difficulty
        })
    except Exception as e:
        logger.error(
            "question_generation_failed category=%s subject=%s error=%s",
            data['category'],
            data['subject'],
            str(e),
            exc_info=True
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
    
    logger.info("evaluating_answer difficulty=%d answer_length=%d", difficulty, len(data['answer']))
    
    try:
        feedback = evaluate_answer(data['question'], data['answer'], difficulty)
        logger.info("answer_evaluated difficulty=%d feedback_length=%d", difficulty, len(feedback))
        return jsonify({'feedback': feedback})
    except Exception as e:
        logger.error("answer_evaluation_failed error=%s", str(e), exc_info=True)
        raise


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

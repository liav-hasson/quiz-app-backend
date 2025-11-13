"""Quiz app REST API."""

from flask import Flask, request, jsonify
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


# Error message template
def error_response(message, code=400):
    """Return error response."""
    return jsonify({"error": message}), code


# Health check route
@app.route("/api/health")
def health():
    """Health check."""
    db_status = "connected" if db_controller and db_controller.db else "disconnected"
    return jsonify({"status": "ok", "database": db_status})


# Returns all categories
@app.route("/api/categories")
def api_categories():
    """Get all categories."""
    try:
        categories = get_categories()
        return jsonify({"categories": categories})
    except Exception as e:
        return error_response(f"Failed to get categories: {str(e)}", 500)


@app.route("/api/subjects")
def api_subjects():
    """Get subjects for category."""
    category = request.args.get("category")
    if not category:
        return error_response("category parameter required")

    try:
        subjects = get_subjects(category)
        return jsonify({"subjects": subjects})
    except Exception as e:
        return error_response(f"Failed to get subjects: {str(e)}", 500)


@app.route("/api/question/generate", methods=["POST"])
def api_generate_question():
    """Generate a question."""
    data = request.get_json()

    try:
        validate_required_fields(data, ["category", "subject", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        return error_response(str(e))

    keyword = get_random_keyword(data["category"], data["subject"])
    if not keyword:
        return error_response("No keywords found", 404)

    question = generate_question(data["category"], keyword, difficulty)

    return jsonify(
        {
            "question": question,
            "keyword": keyword,
            "category": data["category"],
            "subject": data["subject"],
            "difficulty": difficulty,
        }
    )


@app.route("/api/answer/evaluate", methods=["POST"])
def api_evaluate_answer():
    """Evaluate an answer."""
    data = request.get_json()

    try:
        validate_required_fields(data, ["question", "answer", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        return error_response(str(e))

    feedback = evaluate_answer(data["question"], data["answer"], difficulty)
    return jsonify({"feedback": feedback})


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

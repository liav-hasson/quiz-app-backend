"""Quiz routes for quiz-related endpoints.

Routes layer handles HTTP protocol binding only:
- Request/response mapping
- Input validation
- Error to HTTP status code mapping
- Calls QuizController for business logic
"""

import logging
from typing import Optional
from flask import Blueprint, request, jsonify
from controllers.quiz_controller import QuizController
from models.repositories.quiz_repository import QuizRepository
from utils.ai import generate_question, evaluate_answer
from utils.validation.schema import validate_difficulty, validate_required_fields

logger = logging.getLogger(__name__)

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api")

# Will be set by server.py during initialization
quiz_controller: Optional[QuizController] = None


def init_quiz_routes(quiz_repo: QuizRepository):
    """Initialize quiz routes with controller."""
    global quiz_controller
    quiz_controller = QuizController(quiz_repo)


@quiz_bp.route("/categories")
def get_categories_route():
    """Get all categories."""
    try:
        logger.info("get_categories_route")
        categories = quiz_controller.get_categories()
        return jsonify({"categories": categories}), 200
    except Exception as e:
        logger.error("get_categories_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to get categories: {str(e)}"}), 500


@quiz_bp.route("/subjects")
def get_subjects_route():
    """Get subjects for category."""
    category = request.args.get("category")
    
    if not category:
        logger.warning("subjects_request_missing_category")
        return jsonify({"error": "category parameter required"}), 400

    try:
        logger.info("get_subjects_route category=%s", category)
        subjects = quiz_controller.get_subjects(category)
        return jsonify({"subjects": subjects}), 200
    except Exception as e:
        logger.error(
            "get_subjects_failed category=%s error=%s",
            category,
            str(e),
            exc_info=True,
        )
        return jsonify({"error": f"Failed to get subjects: {str(e)}"}), 500


@quiz_bp.route("/all-subjects")
def get_all_subjects_route():
    """Get all subjects for all categories in a single call."""
    try:
        logger.info("get_all_subjects_route")
        data = quiz_controller.get_all_subjects()
        return jsonify({"data": data}), 200
    except Exception as e:
        logger.error("get_all_subjects_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to get all subjects: {str(e)}"}), 500


@quiz_bp.route("/question/generate", methods=["POST"])
def generate_question_route():
    """Generate a question."""
    data = request.get_json()
    
    try:
        validate_required_fields(data, ["category", "subject", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("generate_question_validation_failed error=%s", str(e))
        return jsonify({"error": str(e)}), 400

    try:
        logger.info(
            "generate_question_route category=%s subject=%s difficulty=%d",
            data["category"],
            data["subject"],
            difficulty,
        )
        
        keyword = quiz_controller.get_random_keyword(data["category"], data["subject"])
        if not keyword:
            logger.warning(
                "no_keywords_found category=%s subject=%s",
                data["category"],
                data["subject"],
            )
            return jsonify({"error": "No keywords found for this category and subject"}), 404

        style_modifier = quiz_controller.get_random_style_modifier(data["category"], data["subject"])
        question = generate_question(
            data["category"],
            data["subject"],
            keyword,
            difficulty,
            style_modifier,
        )

        return jsonify({
            "question": question,
            "keyword": keyword,
            "category": data["category"],
            "subject": data["subject"],
            "difficulty": difficulty,
        }), 200
    except Exception as e:
        logger.error(
            "generate_question_failed category=%s subject=%s error=%s",
            data.get("category"),
            data.get("subject"),
            str(e),
            exc_info=True,
        )
        return jsonify({"error": f"Failed to generate question: {str(e)}"}), 500


@quiz_bp.route("/answer/evaluate", methods=["POST"])
def evaluate_answer_route():
    """Evaluate an answer."""
    data = request.get_json()
    
    try:
        validate_required_fields(data, ["question", "answer", "difficulty"])
        difficulty = validate_difficulty(data["difficulty"])
    except ValueError as e:
        logger.warning("evaluate_answer_validation_failed error=%s", str(e))
        return jsonify({"error": str(e)}), 400

    try:
        logger.info("evaluate_answer_route difficulty=%d", difficulty)
        evaluation = evaluate_answer(data["question"], data["answer"], difficulty)
        return jsonify(evaluation), 200
    except Exception as e:
        logger.error("evaluate_answer_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to evaluate answer: {str(e)}"}), 500


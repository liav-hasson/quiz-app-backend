"""Quiz routes for quiz-related endpoints."""

from flask import Blueprint, request, jsonify
from controllers.quiz_controller import QuizController

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api")


@quiz_bp.route("/categories")
def get_categories():
    """Get all categories."""
    response_data, status_code = QuizController.handle_get_categories()
    return jsonify(response_data), status_code


@quiz_bp.route("/subjects")
def get_subjects():
    """Get subjects for category."""
    category = request.args.get("category")
    response_data, status_code = QuizController.handle_get_subjects(category)
    return jsonify(response_data), status_code


@quiz_bp.route("/categories-with-subjects")
def get_categories_with_subjects():
    """Get all categories with their subjects in a single call."""
    response_data, status_code = QuizController.handle_get_categories_with_subjects()
    return jsonify(response_data), status_code


@quiz_bp.route("/question/generate", methods=["POST"])
def generate_question():
    """Generate a question."""
    data = request.get_json()
    response_data, status_code = QuizController.handle_generate_question(data)
    return jsonify(response_data), status_code


@quiz_bp.route("/answer/evaluate", methods=["POST"])
def evaluate_answer():
    """Evaluate an answer."""
    data = request.get_json()
    response_data, status_code = QuizController.handle_evaluate_answer(data)
    return jsonify(response_data), status_code

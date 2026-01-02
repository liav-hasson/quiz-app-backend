"""Quiz routes for quiz-related endpoints.

Routes layer handles HTTP protocol binding only:
- Request/response mapping
- Input validation
- Error to HTTP status code mapping
- Calls QuizController for business logic
"""

import logging
from typing import Optional
from flask import Blueprint, request, jsonify, g
from controllers.quiz_controller import QuizController
from common.repositories.quiz_repository import QuizRepository
from common.utils.ai import get_service
from common.utils.rate_limiter import get_question_limiter, get_evaluation_limiter
from utils.validation.schema import validate_difficulty, validate_required_fields

logger = logging.getLogger(__name__)

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api")

# Will be set by server.py during initialization
quiz_controller: Optional[QuizController] = None

# Rate limiters
question_limiter = get_question_limiter()
evaluation_limiter = get_evaluation_limiter()


def _get_custom_ai_settings():
    """Extract custom AI settings from request headers."""
    custom_api_key = request.headers.get("X-OpenAI-API-Key")
    custom_model = request.headers.get("X-OpenAI-Model")
    return custom_api_key, custom_model


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

    # Rate limiting - get user ID from auth or use IP as fallback
    user = getattr(g, "user", None)
    user_id = user.get("_id") if user else request.remote_addr
    
    allowed, remaining, reset_time = question_limiter.check_rate_limit(
        user_id, "question_generate"
    )
    
    # Add rate limit headers
    headers = {
        "X-RateLimit-Limit": str(question_limiter.config.max_requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }
    
    if not allowed:
        logger.warning(
            "rate_limit_exceeded_question user=%s",
            user_id
        )
        return jsonify({
            "error": "Rate limit exceeded. Please wait before generating more questions.",
            "limit": question_limiter.config.max_requests,
            "window_seconds": question_limiter.config.window_seconds,
            "reset_time": reset_time,
        }), 429, headers

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
            return jsonify({"error": "No keywords found for this category and subject"}), 404, headers

        style_modifier = quiz_controller.get_random_style_modifier(data["category"], data["subject"])
        
        # Get custom AI settings from headers
        custom_api_key, custom_model = _get_custom_ai_settings()
        
        ai_service = get_service()
        question = ai_service.generate_question(
            data["category"],
            data["subject"],
            keyword,
            difficulty,
            style_modifier,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )

        return jsonify({
            "question": question,
            "keyword": keyword,
            "category": data["category"],
            "subject": data["subject"],
            "difficulty": difficulty,
        }), 200, headers
    except Exception as e:
        logger.error(
            "generate_question_failed category=%s subject=%s error=%s",
            data.get("category"),
            data.get("subject"),
            str(e),
            exc_info=True,
        )
        return jsonify({"error": f"Failed to generate question: {str(e)}"}), 500, headers


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

    # Rate limiting - get user ID from auth or use IP as fallback
    user = getattr(g, "user", None)
    user_id = user.get("_id") if user else request.remote_addr
    
    allowed, remaining, reset_time = evaluation_limiter.check_rate_limit(
        user_id, "answer_evaluate"
    )
    
    # Add rate limit headers
    headers = {
        "X-RateLimit-Limit": str(evaluation_limiter.config.max_requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }
    
    if not allowed:
        logger.warning(
            "rate_limit_exceeded_evaluation user=%s",
            user_id
        )
        return jsonify({
            "error": "Rate limit exceeded. Please wait before submitting more answers.",
            "limit": evaluation_limiter.config.max_requests,
            "window_seconds": evaluation_limiter.config.window_seconds,
            "reset_time": reset_time,
        }), 429, headers

    try:
        logger.info("evaluate_answer_route difficulty=%d", difficulty)
        
        # Get custom AI settings from headers
        custom_api_key, custom_model = _get_custom_ai_settings()
        
        ai_service = get_service()
        evaluation = ai_service.evaluate_answer(
            data["question"],
            data["answer"],
            difficulty,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )
        return jsonify(evaluation), 200, headers
    except ValueError as e:
        # ValueError indicates AI response format error
        logger.error("evaluate_answer_format_error error=%s", str(e), exc_info=True)
        return jsonify({
            "error": "Evaluation failed - AI response error",
            "details": str(e)
        }), 422, headers  # 422 Unprocessable Entity
    except Exception as e:
        logger.error("evaluate_answer_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to evaluate answer: {str(e)}"}), 500, headers


@quiz_bp.route("/ai/test", methods=["POST"])
def test_ai_configuration():
    """Test AI configuration with custom API key and model.
    
    Accepts custom settings via headers:
    - X-OpenAI-API-Key: Custom API key
    - X-OpenAI-Model: Custom model name
    
    Makes a simple API call to verify the configuration works.
    """
    from common.utils.ai import OpenAIProvider
    from common.utils.config import get_settings
    
    custom_api_key, custom_model = _get_custom_ai_settings()
    settings = get_settings()
    
    # Determine if we have any API key available (custom or server)
    has_api_key = bool(custom_api_key or settings.openai_api_key or settings.openai_ssm_parameter_name)
    
    if not has_api_key:
        # No API key available at all
        return jsonify({
            "success": False,
            "error": "No OpenAI API key configured. Please provide your API key.",
            "model": None,
            "custom_key": False,
        }), 400
    
    try:
        # Create provider with custom key if provided, otherwise use server config
        provider = OpenAIProvider(api_key=custom_api_key) if custom_api_key else OpenAIProvider()
        
        # Determine which model to test
        model_to_test = custom_model or settings.openai_model or "gpt-4o-mini"
        
        # Use the provider's chat_completion method which handles parameter adaptation
        response = provider.chat_completion(
            model=model_to_test,
            messages=[{"role": "user", "content": "Say 'OK' if you can read this."}],
            max_tokens=10,
        )
        
        result = response.choices[0].message.content.strip() if response.choices else ""
        
        logger.info(
            "ai_config_test_success model=%s custom_key=%s",
            model_to_test,
            "yes" if custom_api_key else "no",
        )
        
        return jsonify({
            "success": True,
            "message": f"Successfully connected to OpenAI using model '{model_to_test}'",
            "model": model_to_test,
            "custom_key": bool(custom_api_key),
            "response": result,
        }), 200
        
    except Exception as e:
        error_message = str(e)
        logger.error("ai_config_test_failed error=%s", error_message)
        
        # Provide helpful error messages
        if "invalid_api_key" in error_message.lower() or "incorrect api key" in error_message.lower():
            return jsonify({
                "success": False,
                "error": "Invalid API key. Please check your OpenAI API key.",
                "model": custom_model,
                "custom_key": bool(custom_api_key),
            }), 400  # Use 400, not 401 - 401 is reserved for session authentication
        elif "model" in error_message.lower() and ("not found" in error_message.lower() or "does not exist" in error_message.lower()):
            return jsonify({
                "success": False,
                "error": f"Model '{custom_model}' not found. Please check the model name.",
                "model": custom_model,
                "custom_key": bool(custom_api_key),
            }), 400
        else:
            return jsonify({
                "success": False,
                "error": f"Configuration test failed: {error_message}",
                "model": custom_model,
                "custom_key": bool(custom_api_key),
            }), 500


@quiz_bp.route("/quiz/perfect-answer", methods=["POST"])
def generate_perfect_answer():
    """Generate a perfect 10/10 answer for a given question.
    
    Request body:
        question (str): The question text
    
    Returns:
        200: {"perfect_answer": "..."}
        400: Missing/invalid input
        500: Generation error
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or "question" not in data:
            return jsonify({
                "error": "Missing required field: question"
            }), 400
        
        question = data["question"].strip()
        if not question:
            return jsonify({
                "error": "Question cannot be empty"
            }), 400
        
        logger.info("generate_perfect_answer_route question_length=%d", len(question))
        
        # Get custom AI settings from headers
        custom_api_key, custom_model = _get_custom_ai_settings()
        
        ai_service = get_service()
        result = ai_service.generate_perfect_answer(
            question,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )
        
        return jsonify(result), 200
        
    except ValueError as e:
        error_message = str(e)
        logger.error("generate_perfect_answer_validation_error error=%s", error_message)
        return jsonify({
            "error": error_message
        }), 400
    except Exception as e:
        error_message = str(e)
        logger.error("generate_perfect_answer_failed error=%s", error_message)
        return jsonify({
            "error": f"Failed to generate perfect answer: {error_message}"
        }), 500
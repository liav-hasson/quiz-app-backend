"""Daily Challenge routes — one question per day, global leaderboard."""

import logging
from typing import Optional

from flask import Blueprint, request, jsonify, g
from common.repositories.daily_challenge_repository import DailyChallengeRepository
from common.repositories.quiz_repository import QuizRepository
from common.repositories.user_repository import UserRepository
from common.utils.ai import get_service

logger = logging.getLogger(__name__)

daily_challenge_bp = Blueprint("daily_challenge", __name__, url_prefix="/api/daily-challenge")

# Set during init
_challenge_repo: Optional[DailyChallengeRepository] = None
_quiz_repo: Optional[QuizRepository] = None
_user_repo: Optional[UserRepository] = None

XP_REWARD = 50  # XP everyone who completes the daily gets


def init_daily_challenge_routes(
    challenge_repo: DailyChallengeRepository,
    quiz_repo: QuizRepository,
    user_repo: UserRepository = None,
) -> None:
    global _challenge_repo, _quiz_repo, _user_repo
    _challenge_repo = challenge_repo
    _quiz_repo = quiz_repo
    _user_repo = user_repo


def _get_custom_ai_settings():
    custom_api_key = request.headers.get("X-OpenAI-API-Key")
    custom_model = request.headers.get("X-OpenAI-Model")
    return custom_api_key, custom_model


def _generate_daily_question(custom_api_key=None, custom_model=None) -> str:
    """Generate a random easy-level question for the daily challenge."""
    import random

    categories = _quiz_repo.get_all_topics()
    if not categories:
        raise RuntimeError("No categories available")
    category = random.choice(categories)

    subjects = _quiz_repo.get_subtopics_by_topic(category)
    if not subjects:
        raise RuntimeError(f"No subjects for category {category}")
    subject = random.choice(subjects)

    keywords = _quiz_repo.get_keywords_by_topic_subtopic(category, subject)
    keyword = random.choice(keywords) if keywords else subject

    style_modifiers = _quiz_repo.get_style_modifiers_by_topic_subtopic(category, subject)
    style_modifier = random.choice(style_modifiers) if style_modifiers else "general explanation"

    ai_service = get_service()
    question = ai_service.generate_question(
        category,
        subject,
        keyword,
        difficulty=1,  # easy
        style_modifier=style_modifier,
        custom_api_key=custom_api_key,
        custom_model=custom_model,
    )
    return question


@daily_challenge_bp.route("", methods=["GET"])
def get_daily_challenge():
    """Return today's challenge question, generating it on first hit."""
    custom_api_key, custom_model = _get_custom_ai_settings()
    user = getattr(g, "user", None)
    user_id = user.get("_id") if user else None

    try:
        challenge = _challenge_repo.get_today_challenge()

        if not challenge:
            # Lazy-generate on first request of the day
            question_text = _generate_daily_question(custom_api_key, custom_model)
            challenge = _challenge_repo.save_challenge(question_text)
            logger.info("daily_challenge_generated date=%s", challenge["date"])

        # Check if user already answered
        user_answer = None
        streak_data = {"current_streak": 0, "active": False}
        if user_id:
            user_answer = _challenge_repo.get_user_answer_today(user_id)
            streak_data = _challenge_repo.get_user_streak(user_id)

        return jsonify({
            "date": challenge["date"],
            "question": challenge["question"],
            "already_answered": user_answer is not None,
            "user_answer": user_answer,
            "xp_reward": XP_REWARD,
            "streak": streak_data,
        }), 200

    except Exception as e:
        logger.error("daily_challenge_get_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to get daily challenge: {str(e)}"}), 500


@daily_challenge_bp.route("/answer", methods=["POST"])
def submit_daily_answer():
    """Submit and evaluate the user's answer for today's challenge."""
    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = user.get("_id")
    username = user.get("username", "Anonymous")

    # Prevent double submission
    existing = _challenge_repo.get_user_answer_today(user_id)
    if existing:
        return jsonify({
            "error": "Already answered today's challenge",
            "user_answer": existing,
        }), 409

    data = request.get_json()
    answer = (data or {}).get("answer", "").strip()
    if not answer:
        return jsonify({"error": "Answer cannot be empty"}), 400

    challenge = _challenge_repo.get_today_challenge()
    if not challenge:
        return jsonify({"error": "No daily challenge available"}), 404

    custom_api_key, custom_model = _get_custom_ai_settings()

    try:
        ai_service = get_service()
        evaluation = ai_service.evaluate_answer(
            challenge["question"],
            answer,
            difficulty=1,
            custom_api_key=custom_api_key,
            custom_model=custom_model,
        )

        score = evaluation.get("score", 0)
        feedback = evaluation.get("feedback", "")

        _challenge_repo.save_user_answer(
            user_id=user_id,
            username=username,
            answer=answer,
            score=score,
            feedback=feedback,
        )

        # Auto-award XP
        xp_awarded = False
        if _user_repo:
            xp_awarded = _user_repo.add_bonus_xp(user_id, XP_REWARD)

        # Update daily streak
        streak = 0
        if _challenge_repo:
            streak = _challenge_repo.update_user_streak(user_id)

        logger.info(
            "daily_challenge_answered user=%s score=%s xp_awarded=%s streak=%s",
            user_id, score, xp_awarded, streak,
        )

        return jsonify({
            "score": score,
            "feedback": feedback,
            "xp_reward": XP_REWARD,
            "xp_awarded": xp_awarded,
            "streak": streak,
        }), 200

    except Exception as e:
        logger.error("daily_challenge_answer_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to evaluate answer: {str(e)}"}), 500


@daily_challenge_bp.route("/leaderboard", methods=["GET"])
def get_daily_leaderboard():
    """Return today's daily challenge leaderboard."""
    try:
        leaderboard = _challenge_repo.get_today_leaderboard()
        return jsonify({"leaderboard": leaderboard}), 200
    except Exception as e:
        logger.error("daily_leaderboard_failed error=%s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@daily_challenge_bp.route("/streak", methods=["GET"])
def get_daily_streak():
    """Return the current user's daily challenge streak."""
    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = user.get("_id")
    try:
        streak_data = _challenge_repo.get_user_streak(user_id)
        return jsonify(streak_data), 200
    except Exception as e:
        logger.error("daily_streak_get_failed error=%s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@daily_challenge_bp.route("/history", methods=["GET"])
def get_daily_history():
    """Return the current user's past daily challenge answers."""
    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = user.get("_id")
    limit = min(int(request.args.get("limit", 10)), 50)

    try:
        history = _challenge_repo.get_user_history(user_id, limit=limit)
        return jsonify({"history": history}), 200
    except Exception as e:
        logger.error("daily_history_get_failed error=%s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

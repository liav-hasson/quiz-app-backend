"""Daily Deep Dive routes — daily AI-generated educational article."""

import logging
import random
from typing import Optional

from flask import Blueprint, request, jsonify, g
from common.repositories.daily_deep_dive_repository import DailyDeepDiveRepository
from common.repositories.quiz_repository import QuizRepository
from common.repositories.user_repository import UserRepository
from common.utils.ai import get_service

logger = logging.getLogger(__name__)

daily_deep_dive_bp = Blueprint("daily_deep_dive", __name__, url_prefix="/api/daily-deep-dive")

# Set during init
_deep_dive_repo: Optional[DailyDeepDiveRepository] = None
_quiz_repo: Optional[QuizRepository] = None
_user_repo: Optional[UserRepository] = None

XP_REWARD = 25


def init_daily_deep_dive_routes(
    deep_dive_repo: DailyDeepDiveRepository,
    quiz_repo: QuizRepository,
    user_repo: UserRepository = None,
) -> None:
    global _deep_dive_repo, _quiz_repo, _user_repo
    _deep_dive_repo = deep_dive_repo
    _quiz_repo = quiz_repo
    _user_repo = user_repo


def _get_custom_ai_settings():
    custom_api_key = request.headers.get("X-OpenAI-API-Key")
    custom_model = request.headers.get("X-OpenAI-Model")
    return custom_api_key, custom_model


def _generate_daily_article(custom_api_key=None, custom_model=None) -> dict:
    """Pick a random keyword and generate a deep dive article.

    Returns:
        dict with keys: keyword, category, subject, content
    """
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

    ai_service = get_service()
    content = ai_service.generate_deep_dive(
        category,
        subject,
        keyword,
        custom_api_key=custom_api_key,
        custom_model=custom_model,
    )
    return {
        "keyword": keyword,
        "category": category,
        "subject": subject,
        "content": content,
    }


@daily_deep_dive_bp.route("", methods=["GET"])
def get_daily_deep_dive():
    """Return today's deep dive article, generating it on first hit."""
    custom_api_key, custom_model = _get_custom_ai_settings()
    user = getattr(g, "user", None)
    user_id = user.get("_id") if user else None

    try:
        article = _deep_dive_repo.get_today_article()

        if not article:
            generated = _generate_daily_article(custom_api_key, custom_model)
            article = _deep_dive_repo.save_article(
                keyword=generated["keyword"],
                category=generated["category"],
                subject=generated["subject"],
                content=generated["content"],
            )
            logger.info("daily_deep_dive_generated date=%s keyword=%s", article["date"], article["keyword"])

        xp_claimed = False
        if user_id:
            xp_claimed = _deep_dive_repo.has_user_claimed_xp(user_id)

        return jsonify({
            "date": article["date"],
            "keyword": article["keyword"],
            "category": article["category"],
            "subject": article["subject"],
            "content": article["content"],
            "xp_reward": XP_REWARD,
            "xp_claimed": xp_claimed,
        }), 200

    except Exception as e:
        logger.error("daily_deep_dive_get_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to get daily deep dive: {str(e)}"}), 500


@daily_deep_dive_bp.route("/claim-xp", methods=["POST"])
def claim_deep_dive_xp():
    """Claim XP for reading today's deep dive article (one-time per user)."""
    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    user_id = user.get("_id")

    # Check article exists for today
    article = _deep_dive_repo.get_today_article()
    if not article:
        return jsonify({"error": "No deep dive article available today"}), 404

    # Prevent double claim
    if _deep_dive_repo.has_user_claimed_xp(user_id):
        return jsonify({"error": "XP already claimed for today's article"}), 409

    try:
        _deep_dive_repo.claim_xp(user_id)

        xp_awarded = False
        if _user_repo:
            xp_awarded = _user_repo.add_bonus_xp(user_id, XP_REWARD)

        logger.info(
            "daily_deep_dive_xp_claimed user=%s xp_awarded=%s",
            user_id, xp_awarded,
        )

        return jsonify({
            "xp_reward": XP_REWARD,
            "xp_awarded": xp_awarded,
        }), 200

    except Exception as e:
        logger.error("daily_deep_dive_claim_xp_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to claim XP: {str(e)}"}), 500


@daily_deep_dive_bp.route("/archive", methods=["GET"])
def get_deep_dive_archive():
    """Return paginated archive of past deep dive articles."""
    try:
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)
        skip = (page - 1) * limit

        articles = _deep_dive_repo.get_archive(limit=limit, skip=skip)
        total = _deep_dive_repo.get_archive_count()

        return jsonify({
            "articles": articles,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": skip + limit < total,
        }), 200

    except Exception as e:
        logger.error("daily_deep_dive_archive_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to get archive: {str(e)}"}), 500

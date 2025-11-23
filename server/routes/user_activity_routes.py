"""User activity routes for answer submission and leaderboard."""

import logging
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request, g, current_app
from controllers.user_activity_handler import UserActivityController
from models.repositories.user_repository import UserRepository
from models.repositories.questions_repository import QuestionsRepository
from models.repositories.leaderboard_repository import LeaderboardRepository
from utils.validation.schema import (
    validate_difficulty,
    validate_required_fields,
    MIN_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    DEFAULT_HISTORY_LIMIT,
)

logger = logging.getLogger(__name__)

user_activity_bp = Blueprint("user_activity", __name__, url_prefix="/api/user")

# Will be set by server.py during initialization
activity_controller: Optional[UserActivityController] = None


def init_user_activity_routes(
    user_repository: UserRepository,
    questions_repository: QuestionsRepository,
    leaderboard_repository: LeaderboardRepository,
):
    """Initialize user activity routes with controllers."""
    global activity_controller
    activity_controller = UserActivityController(
        user_repository, questions_repository, leaderboard_repository
    )


@user_activity_bp.route("/answers", methods=["POST"])
def save_answer():
    """Save a user's answer to a question for statistics tracking."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    data = request.get_json(silent=True) or {}
    authenticated_user = getattr(g, "user", None)

    if not authenticated_user and not current_app.config.get("TESTING"):
        return jsonify({"error": "Authentication required"}), 401

    try:
        answer_id = activity_controller.save_user_answer(
            data,
            authenticated_user=authenticated_user,
        )
        return jsonify({"answer_id": answer_id}), 201
    except ValueError as exc:
        logger.warning("save_answer_validation_failed error=%s", str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("answer_save_failed error=%s", str(exc), exc_info=True)
        return jsonify({"error": f"Failed to save answer: {str(exc)}"}), 500


@user_activity_bp.route("/history", methods=["GET"])
def get_history():
    """Return the authenticated user's question history."""

    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    authenticated_user = getattr(g, "user", None)
    if not authenticated_user and not current_app.config.get("TESTING"):
        return jsonify({"error": "Authentication required"}), 401

    try:
        limit = int(request.args.get("limit", DEFAULT_HISTORY_LIMIT))
        before_param = request.args.get("before")
        before = None
        if before_param:
            try:
                before = datetime.fromisoformat(before_param)
            except ValueError:
                logger.warning("invalid_before_timestamp value=%s", before_param)

        history = activity_controller.get_user_history(
            authenticated_user=authenticated_user,
            user_id=request.args.get("user_id"),
            email=request.args.get("email"),
            limit=min(max(limit, MIN_HISTORY_LIMIT), MAX_HISTORY_LIMIT),
            before=before,
        )
        return jsonify({"history": history, "count": len(history)}), 200
    except ValueError as exc:
        logger.warning("history_fetch_validation_failed error=%s", str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("history_fetch_failed error=%s", str(exc), exc_info=True)
        return jsonify({"error": "Failed to fetch user history"}), 500


@user_activity_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """Get top 10 users by score (leaderboard)."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    try:
        leaderboard = activity_controller.get_leaderboard()
        return jsonify({"leaderboard": leaderboard, "count": len(leaderboard)}), 200
    except Exception as e:
        logger.error("leaderboard_fetch_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to fetch leaderboard: {str(e)}"}), 500


@user_activity_bp.route("/leaderboard/update", methods=["POST"])
def update_leaderboard():
    """Update leaderboard by calculating user's average score (exp/count)."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    data = request.get_json()
    try:
        result = activity_controller.update_leaderboard_entry(
            user_id=data["user_id"], username=data["username"]
        )
        return jsonify(result), 201
    except ValueError as e:
        logger.warning("user_not_found username=%s", data.get("username"))
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error("leaderboard_update_failed error=%s", str(e), exc_info=True)
        return jsonify({"error": f"Failed to update leaderboard: {str(e)}"}), 500

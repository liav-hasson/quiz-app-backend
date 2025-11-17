"""User activity routes for answer tracking and leaderboard."""

from flask import Blueprint, request, jsonify
from typing import Optional
from controllers.user_activity_controller import UserActivityController

user_activity_bp = Blueprint("user_activity", __name__, url_prefix="/api")

# Will be set by server.py during initialization
activity_controller: Optional[UserActivityController] = None


def init_user_activity_routes(
    user_controller, questions_controller, toptens_controller
):
    """Initialize user activity routes with controllers."""
    global activity_controller
    activity_controller = UserActivityController(
        user_controller, questions_controller, toptens_controller
    )


@user_activity_bp.route("/answers", methods=["POST"])
def save_answer():
    """Save a user's answer to a question for statistics tracking."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    data = request.get_json()
    response_data, status_code = activity_controller.handle_save_answer(data)
    return jsonify(response_data), status_code


@user_activity_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """Get top 10 users by score (leaderboard)."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    response_data, status_code = activity_controller.handle_get_leaderboard()
    return jsonify(response_data), status_code


@user_activity_bp.route("/leaderboard/update", methods=["POST"])
def update_leaderboard():
    """Update leaderboard by calculating user's average score (exp/count)."""
    if activity_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    data = request.get_json()
    response_data, status_code = activity_controller.handle_update_leaderboard(data)
    return jsonify(response_data), status_code

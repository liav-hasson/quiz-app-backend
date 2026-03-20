"""Account management routes (requires authentication)."""

import logging
from typing import Optional

from flask import Blueprint, g, jsonify, request

from controllers.account_controller import AccountController
from common.repositories.questions_repository import QuestionsRepository
from common.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

account_bp = Blueprint("account", __name__, url_prefix="/api/account")

account_controller: Optional[AccountController] = None


def init_account_routes(
    user_repository: UserRepository,
    questions_repository: QuestionsRepository,
) -> None:
    """Initialize account routes with required repositories."""
    global account_controller
    account_controller = AccountController(user_repository, questions_repository)


@account_bp.route("/info", methods=["GET"])
def get_info():
    """Return the authenticated user's account information."""
    if account_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data, status = account_controller.get_account_info(user)
    return jsonify(data), status


@account_bp.route("/username", methods=["PATCH"])
def change_username():
    """Change the authenticated user's username."""
    if account_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    new_username = body.get("username", "").strip()
    if not new_username:
        return jsonify({"error": "Username is required"}), 400

    data, status = account_controller.change_username(user, new_username)
    return jsonify(data), status


@account_bp.route("/password", methods=["PATCH"])
def change_password():
    """Change the authenticated user's password (credentials accounts only)."""
    if account_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    current_password = body.get("currentPassword", "")
    new_password = body.get("newPassword", "")

    if not current_password or not new_password:
        return jsonify({"error": "Both currentPassword and newPassword are required"}), 400

    data, status = account_controller.change_password(user, current_password, new_password)
    return jsonify(data), status


@account_bp.route("", methods=["DELETE"])
def delete_account():
    """Permanently delete the authenticated user's account and all data."""
    if account_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    user = getattr(g, "user", None)
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    password = body.get("password")

    data, status = account_controller.delete_account(user, password)
    return jsonify(data), status

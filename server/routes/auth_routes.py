"""Authentication routes for OAuth and user authentication."""

from flask import Blueprint, request, jsonify
from typing import Optional
from controllers.auth_controller import AuthController

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Will be set by server.py during initialization
auth_controller: Optional[AuthController] = None


def init_auth_routes(oauth_instance, user_controller):
    """Initialize auth routes with OAuth and controllers."""
    global auth_controller
    auth_controller = AuthController(user_controller, oauth_instance)


@auth_bp.route("/login")
def login():
    """Start Google OAuth login flow."""
    if auth_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    result, status_code = auth_controller.handle_login(request.url_root)
    if status_code == 200:
        return result
    return jsonify(result), status_code


@auth_bp.route("/callback")
def callback():
    """Handle Google OAuth callback and create/update user."""
    if auth_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    response_data, status_code = auth_controller.handle_callback()
    return jsonify(response_data), status_code

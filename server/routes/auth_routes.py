"""Authentication routes for OAuth and user authentication."""

from flask import Blueprint, request, jsonify
from typing import Optional
from controllers.auth_handler import AuthController
from controllers.user_activity_handler import UserActivityController
from models.repositories.user_repository import UserRepository
from utils.identity import GoogleTokenVerifier, TokenService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Will be set by server.py during initialization
auth_controller: Optional[AuthController] = None


def init_auth_routes(
    oauth_instance,
    user_repository: UserRepository,
    token_service: TokenService,
    google_verifier: GoogleTokenVerifier,
    user_activity_controller: Optional[UserActivityController] = None,
):
    """Initialize auth routes with OAuth and controllers."""

    global auth_controller
    auth_controller = AuthController(
        user_repository,
        token_service,
        google_verifier,
        user_activity_controller,
        oauth_instance,
    )


@auth_bp.route("/google-login", methods=["POST"])
def google_token_login():
    """Handle Google ID token from frontend and issue application JWT."""
    if auth_controller is None:
        return jsonify({"error": "Service not initialized"}), 503

    data = request.get_json()
    if not data or "credential" not in data:
        return jsonify({"error": "Missing credential in request body"}), 400

    google_id_token = data["credential"]
    response_data, status_code = auth_controller.handle_google_token_login(
        google_id_token
    )
    return jsonify(response_data), status_code

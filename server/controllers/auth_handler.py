"""Authentication controller for handling OAuth and user authentication."""

import logging
from typing import Dict, Any, Optional, Tuple

from utils.identity import (
    GoogleClientNotConfiguredError,
    GoogleTokenVerifier,
    GoogleVerificationError,
    InvalidGoogleTokenError,
    TokenService,
)

logger = logging.getLogger(__name__)


class AuthController:
    """Controller for authentication operations.

    Implements OAuth2 token verification flow for Google authentication.
    Frontend obtains Google ID token via Google JavaScript SDK and sends it to
    handle_google_token_login() for verification and app JWT issuance.
    """

    def __init__(
        self,
        user_repository,
        token_service: TokenService,
        google_verifier: GoogleTokenVerifier,
        user_activity_controller=None,
        oauth_instance=None,
    ):
        """Initialize auth controller with injected services."""

        self.user_repository = user_repository
        self.token_service = token_service
        self.google_verifier = google_verifier
        self.user_activity_controller = user_activity_controller
        self.oauth = oauth_instance

    def handle_google_token_login(
        self, google_id_token: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Handle Google ID token from frontend and issue application JWT.

        This method verifies the Google ID token sent from the frontend,
        extracts user information, and returns your application's JWT token.

        Args:
            google_id_token: The Google ID token received from frontend

        Returns:
            Tuple of (response_data, status_code)
            Response contains: email, name, picture, token (your JWT)
        """
        try:
            try:
                idinfo = self.google_verifier.verify(google_id_token)
            except GoogleClientNotConfiguredError:
                return {"error": "OAuth not properly configured"}, 500
            except InvalidGoogleTokenError as exc:
                return {"error": str(exc)}, 401
            except GoogleVerificationError as exc:
                logger.error("google_token_verification_failed error=%s", str(exc))
                return {"error": "Failed to verify Google token"}, 500

            # Extract user information from verified token
            google_id = idinfo.get("sub")
            email = idinfo.get("email")
            name = idinfo.get("name")
            picture = idinfo.get("picture")
            email_verified = idinfo.get("email_verified", False)

            if not google_id or not email:
                logger.warning("incomplete_google_token_data")
                return {"error": "Incomplete user information from Google"}, 400

            if not email_verified:
                logger.warning("unverified_email email=%s", email)
                return {"error": "Email not verified by Google"}, 400

            logger.info("google_token_verified google_id=%s email=%s", google_id, email)

            # Create or update user in database
            user = self.user_repository.create_or_update_google_user(
                google_id=google_id, email=email, name=name, picture=picture
            )

            # Check and reset streak if user hasn't been active
            if self.user_activity_controller:
                streak_result = (
                    self.user_activity_controller.check_and_reset_streak_on_login(user)
                )
                if streak_result["was_reset"]:
                    logger.info(
                        "streak_reset_on_login user_id=%s days_since=%d",
                        user.get("_id"),
                        streak_result["days_since_last_activity"],
                    )
                    # Update user object with new streak
                    user["streak"] = 0

            # Generate your application's JWT token
            app_token = self.token_service.generate(user)

            logger.info(
                "token_login_successful user_id=%s email=%s streak=%d",
                user.get("_id"),
                email,
                user.get("streak", 0),
            )

            # Return the response in your desired format
            return {
                "email": email,
                "name": name,
                "picture": picture,
                "token": app_token,
                "streak": user.get("streak", 0),
            }, 200

        except Exception as e:
            logger.error("google_token_login_failed error=%s", str(e), exc_info=True)
            return {"error": "Failed to process Google token"}, 500

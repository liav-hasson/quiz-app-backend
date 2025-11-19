"""Authentication controller for handling OAuth and user authentication."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests

logger = logging.getLogger(__name__)


class AuthController:
    """Controller for authentication operations."""

    def __init__(self, user_controller, oauth_instance=None):
        """Initialize auth controller with user controller dependency."""
        self.user_controller = user_controller
        self.oauth = oauth_instance

    def set_oauth(self, oauth_instance):
        """Set OAuth instance (called during initialization)."""
        self.oauth = oauth_instance

    def handle_login(self, request_url_root: str, data: dict) -> Tuple[Any, int]:
        """
        Handle login with Google user data sent directly from frontend.
        """
        try:
            google_id = data.get("id")
            email = data.get("email")
            name = data.get("name")

            if not google_id or not email:
                return {"error": "google_id and email are required"}, 400

            # --- Check if user exists (by google_id or email) ---
            user = self.user_controller.create_or_update_google_user(
                google_id=google_id,
                email=email,
                name=name,
            )

            # Return the user object
            return user, 200

        except Exception as e:
            logger.error("login_failed %s", str(e), exc_info=True)
            return {"error": "Internal login error"}, 500

    def handle_callback(self) -> Tuple[Dict[str, Any], int]:
        """
        Handle OAuth callback request.

        Returns:
            Tuple of (response_data, status_code)
        """
        if self.oauth is None:
            logger.error("oauth_not_initialized")
            return {"error": "Service not properly initialized"}, 500

        try:
            token = self.oauth.google.authorize_access_token()  # type: ignore

            # Try to parse ID token (OIDC) or fetch userinfo
            try:
                user_info = self.oauth.google.parse_id_token(token)  # type: ignore
            except Exception:
                resp = self.oauth.google.get("userinfo")  # type: ignore
                user_info = resp.json()

            google_id = user_info.get("sub")
            email = user_info.get("email")
            name = user_info.get("name")
            picture = user_info.get("picture")

            if not google_id or not email:
                return {"error": "Failed to obtain user info from provider"}, 400

            # Process OAuth callback
            result = self.process_google_oauth_callback(
                google_id=google_id, email=email, name=name, picture=picture
            )

            return result, 200

        except ValueError as e:
            logger.error("oauth_callback_processing_failed %s", str(e), exc_info=True)
            return {"error": str(e)}, 500
        except Exception as e:
            logger.error("oauth_callback_failed %s", str(e), exc_info=True)
            return {"error": "OAuth callback failed"}, 500

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
            # Get Google OAuth client ID from environment
            google_client_id = os.getenv("GOOGLE_CLIENT_ID")
            if not google_client_id:
                logger.error("google_client_id_not_configured")
                return {"error": "OAuth not properly configured"}, 500

            # Verify the Google ID token
            try:
                idinfo = id_token.verify_oauth2_token(
                    google_id_token, requests.Request(), google_client_id
                )
            except ValueError as e:
                logger.warning("invalid_google_token error=%s", str(e))
                return {"error": "Invalid Google token"}, 401

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
            user = self.user_controller.create_or_update_google_user(
                google_id=google_id, email=email, name=name, picture=picture
            )

            # Generate your application's JWT token
            app_token = self._generate_jwt(user)

            logger.info(
                "token_login_successful user_id=%s email=%s", user.get("_id"), email
            )

            # Return the response in your desired format
            return {
                "email": email,
                "name": name,
                "picture": picture,
                "token": app_token,
            }, 200

        except Exception as e:
            logger.error("google_token_login_failed error=%s", str(e), exc_info=True)
            return {"error": "Failed to process Google token"}, 500

    def process_google_oauth_callback(
        self,
        google_id: str,
        email: str,
        name: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process Google OAuth callback and create/update user.

        Args:
            google_id: Google user ID
            email: User's email
            name: User's name (optional)
            picture: User's profile picture URL (optional)

        Returns:
            Dictionary with JWT token and user data

        Raises:
            ValueError: If user creation/update fails
        """
        logger.info("processing_google_oauth google_id=%s email=%s", google_id, email)

        try:
            # Create or update user in DB
            user = self.user_controller.create_or_update_google_user(
                google_id=google_id, email=email, name=name, picture=picture
            )

            # Issue JWT for the user
            token = self._generate_jwt(user)

            logger.info(
                "oauth_user_authenticated user_id=%s email=%s", user.get("_id"), email
            )

            return {"token": token, "user": user}

        except Exception as e:
            logger.error(
                "oauth_processing_failed google_id=%s error=%s",
                google_id,
                str(e),
                exc_info=True,
            )
            raise ValueError(f"Failed to process OAuth callback: {str(e)}")

    def _generate_jwt(self, user: Dict[str, Any]) -> str:
        """
        Generate JWT token for authenticated user.

        Args:
            user: User data dictionary

        Returns:
            JWT token string
        """
        jwt_secret = os.getenv("JWT_SECRET", "devsecret")
        jwt_exp_days = int(os.getenv("JWT_EXP_DAYS", "7"))

        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.get("_id"),
            "email": user.get("email"),
            "name": user.get("name"),
            "exp": now + timedelta(days=jwt_exp_days),
            "iat": now,
        }

        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        logger.debug(
            "jwt_generated user_id=%s exp_days=%d", user.get("_id"), jwt_exp_days
        )

        return token

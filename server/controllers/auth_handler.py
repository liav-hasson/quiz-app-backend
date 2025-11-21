"""Authentication controller for handling OAuth and user authentication."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import jwt
import pytz
from google.oauth2 import id_token
from google.auth.transport import requests
from utils.config import get_jwt_secret, get_google_client_id

logger = logging.getLogger(__name__)


class AuthController:
    """Controller for authentication operations.
    
    This controller implements modern OAuth2 token verification flow for Google authentication.
    It has been simplified to use only the direct token verification method
    (handle_google_token_login) which is optimal for single-page applications (SPAs).
    
    Removed methods:
    - handle_callback(): Legacy OAuth Authorization Code Flow endpoint.
      Was used for traditional redirect-based OAuth but incompatible with modern SPA architecture.
      Frontend now directly obtains Google ID token via Google JavaScript SDK and sends it to 
      handle_google_token_login() for verification and app JWT issuance. This is more efficient 
      (no redirect round-trip) and better suited for SPAs.
    """

    def __init__(self, user_controller, oauth_instance=None):
        """Initialize auth controller with user controller dependency."""
        self.user_controller = user_controller
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
            # Get Google OAuth client ID from SSM Parameter Store or environment variable
            google_client_id = get_google_client_id()
            if not google_client_id:
                logger.error("google_client_id_not_configured")
                return {"error": "OAuth not properly configured"}, 500

            # Verify the Google ID token using the google auth library
            # on success returns a dict with verified claims
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
            # Function defined in "models/user_model.py"
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
            # Function defined in "models/user_model.py"
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
        # secret is in ssm parameter store "/quiz-app/jwt-secret"
        # function defined in config.py
        jwt_secret = get_jwt_secret()
        jwt_exp_days = int(os.getenv("JWT_EXP_DAYS", "7"))

        # Use Jerusalem timezone (Asia/Jerusalem)
        jerusalem_tz = pytz.timezone('Asia/Jerusalem')
        now = datetime.now(jerusalem_tz)
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

"""Authentication controller for handling OAuth and user authentication."""

import logging
from typing import Dict, Any, Optional, Tuple

from common.utils.identity import (
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
                "id": str(user.get("_id")),  # Add user ID for frontend
                "email": email,
                "name": name,
                "username": name,  # Add username alias
                "picture": picture,
                "token": app_token,
                "streak": user.get("streak", 0),
            }, 200

        except Exception as e:
            logger.error("google_token_login_failed error=%s", str(e), exc_info=True)
            return {"error": "Failed to process Google token"}, 500

    def handle_guest_login(self, username: str) -> Tuple[Dict[str, Any], int]:
        """Handle guest login - create or retrieve user without OAuth.

        Creates a new guest user if username doesn't exist, or returns
        existing user if they've logged in before. Guest users have
        auth_type='guest' and use DiceBear for avatar generation.

        Args:
            username: The desired username (already validated by route)

        Returns:
            Tuple of (response_data, status_code)
            Response contains: id, email, name, username, picture, token, streak
        """
        from datetime import datetime

        try:
            # Check if guest user with this username already exists
            existing_user_doc = self.user_repository.collection.find_one(
                {"username": username, "auth_type": "guest"}
            )

            if existing_user_doc:
                # Existing guest user - generate new token and normalize XP/counts
                mongo_id = existing_user_doc.get("_id")
                if mongo_id is not None:
                    self.user_repository.collection.update_one(
                        {"_id": mongo_id},
                        {"$set": {"experience": 0, "questions_count": 0}},
                    )

                existing_user_doc["experience"] = 0
                existing_user_doc["questions_count"] = 0
                existing_user_doc["_id"] = str(existing_user_doc["_id"])
                user = existing_user_doc
                logger.info(
                    "guest_login_existing user_id=%s username=%s",
                    user["_id"],
                    username,
                )
            else:
                # Check if username is taken by a Google user
                google_user = self.user_repository.collection.find_one(
                    {"username": username}
                )
                if google_user:
                    return {"error": "Username already taken"}, 409

                # Create new guest user
                now = datetime.now()

                user_doc = {
                    "username": username,
                    "email": f"{username}@guest.quizlabs.local",  # Placeholder email
                    "name": username,
                    "picture": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
                    "auth_type": "guest",
                    "experience": 0,
                    "questions_count": 0,
                    "streak": 0,
                    "last_activity_date": None,
                    "created_at": now,
                    "updated_at": now,
                }

                result = self.user_repository.collection.insert_one(user_doc)
                user = self.user_repository.collection.find_one(
                    {"_id": result.inserted_id}
                )
                user["_id"] = str(user["_id"])
                logger.info(
                    "guest_login_created user_id=%s username=%s", user["_id"], username
                )

            # Check and reset streak if needed
            if self.user_activity_controller:
                streak_result = (
                    self.user_activity_controller.check_and_reset_streak_on_login(user)
                )
                if streak_result["was_reset"]:
                    user["streak"] = 0

            # Generate JWT token
            app_token = self.token_service.generate(user)

            return {
                "id": str(user.get("_id")),
                "email": user.get("email"),
                "name": user.get("name"),
                "username": user.get("username"),
                "picture": user.get("picture"),
                "token": app_token,
                "streak": user.get("streak", 0),
                "experience": user.get("experience", 0),
                "questions_count": user.get("questions_count", 0),
                "auth_type": "guest",
            }, 200

        except Exception as e:
            logger.error("guest_login_failed error=%s", str(e), exc_info=True)
            return {"error": "Failed to process guest login"}, 500

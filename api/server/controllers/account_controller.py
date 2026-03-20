"""Account management controller for profile updates and deletion."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

import bcrypt

from common.repositories.questions_repository import QuestionsRepository
from common.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8
PASSWORD_PATTERN_UPPERCASE = re.compile(r"[A-Z]")
PASSWORD_PATTERN_LOWERCASE = re.compile(r"[a-z]")
PASSWORD_PATTERN_DIGIT = re.compile(r"\d")
PASSWORD_PATTERN_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]")

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{2,30}$")


class AccountController:
    """Handles account info retrieval, username/password changes, and deletion."""

    def __init__(
        self,
        user_repository: UserRepository,
        questions_repository: QuestionsRepository,
    ) -> None:
        self.user_repository = user_repository
        self.questions_repository = questions_repository

    @staticmethod
    def _validate_password(password: str) -> Optional[str]:
        if len(password) < MIN_PASSWORD_LENGTH:
            return f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        if not PASSWORD_PATTERN_UPPERCASE.search(password):
            return "Password must contain at least one uppercase letter"
        if not PASSWORD_PATTERN_LOWERCASE.search(password):
            return "Password must contain at least one lowercase letter"
        if not PASSWORD_PATTERN_DIGIT.search(password):
            return "Password must contain at least one digit"
        if not PASSWORD_PATTERN_SPECIAL.search(password):
            return "Password must contain at least one special character"
        return None

    def get_account_info(self, user: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Return public account information for the authenticated user."""
        return {
            "id": str(user.get("_id")),
            "username": user.get("username"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "auth_type": user.get("auth_type", "google"),
            "created_at": str(user.get("created_at", "")),
            "experience": user.get("experience", 0),
            "questions_count": user.get("questions_count", 0),
            "streak": user.get("streak", 0),
        }, 200

    def change_username(
        self, user: Dict[str, Any], new_username: str
    ) -> Tuple[Dict[str, Any], int]:
        """Change the authenticated user's username."""
        if not new_username or not USERNAME_PATTERN.match(new_username):
            return {
                "error": "Username must be 2-30 characters (letters, numbers, _ and - only)"
            }, 400

        user_id = str(user.get("_id"))
        try:
            self.user_repository.update_username(user_id, new_username)
        except ValueError as exc:
            return {"error": str(exc)}, 409

        logger.info("username_changed user_id=%s new_username=%s", user_id, new_username)
        return {"message": "Username updated", "username": new_username}, 200

    def change_password(
        self,
        user: Dict[str, Any],
        current_password: str,
        new_password: str,
    ) -> Tuple[Dict[str, Any], int]:
        """Change password for a credentials-based user."""
        auth_type = user.get("auth_type", "google")
        if auth_type != "credentials":
            return {"error": "Password change is only available for credential accounts"}, 400

        stored_hash = user.get("hashed_password")
        if not stored_hash:
            return {"error": "No password set for this account"}, 400

        if not bcrypt.checkpw(current_password.encode("utf-8"), stored_hash.encode("utf-8")):
            return {"error": "Current password is incorrect"}, 401

        pw_error = self._validate_password(new_password)
        if pw_error:
            return {"error": pw_error}, 400

        new_hash = bcrypt.hashpw(
            new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        user_id = str(user.get("_id"))
        self.user_repository.update_password(user_id, new_hash)

        logger.info("password_changed user_id=%s", user_id)
        return {"message": "Password updated"}, 200

    def delete_account(
        self, user: Dict[str, Any], password: Optional[str] = None
    ) -> Tuple[Dict[str, Any], int]:
        """Permanently delete the user's account and all associated data.

        For credentials users, the current password must be provided.
        For Google users, no password is required (just confirmation).
        """
        auth_type = user.get("auth_type", "google")
        user_id = str(user.get("_id"))

        # Verify password for credential accounts
        if auth_type == "credentials":
            stored_hash = user.get("hashed_password")
            if not password or not stored_hash:
                return {"error": "Password is required to delete a credential account"}, 400
            if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                return {"error": "Incorrect password"}, 401

        # Delete all user quiz data
        deleted_questions = self.questions_repository.delete_questions_by_user(user_id)
        logger.info("account_data_deleted user_id=%s questions=%d", user_id, deleted_questions)

        # Delete the user document
        self.user_repository.delete_user_by_id(user_id)
        logger.info("account_deleted user_id=%s auth_type=%s", user_id, auth_type)

        return {"message": "Account deleted"}, 200

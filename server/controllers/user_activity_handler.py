"""User activity controller for tracking answers and leaderboard."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.validation.schema import validate_difficulty, validate_required_fields

logger = logging.getLogger(__name__)


class UserActivityController:
    """Controller for user activity tracking (answers, leaderboard)."""

    def __init__(
        self, user_repository, questions_repository, leaderboard_repository
    ):
        """Initialize with repository dependencies."""
        self.user_repository = user_repository
        self.questions_repository = questions_repository
        self.leaderboard_repository = leaderboard_repository

    def save_user_answer(
        self,
        payload: Dict[str, Any],
        authenticated_user: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a user's answer and update their statistics."""

        validate_required_fields(
            payload,
            ["question", "answer", "difficulty", "category", "subject"],
        )
        difficulty = validate_difficulty(payload["difficulty"])

        user = self._resolve_user(
            authenticated_user,
            user_id=payload.get("user_id"),
            username=payload.get("username"),
            email=payload.get("email") or payload.get("user_email"),
        )

        answer_text = payload["answer"]
        score = self._normalize_score(payload.get("score"), payload.get("evaluation"))
        evaluation = payload.get("evaluation") or {}
        keyword = payload.get("keyword", "")
        metadata = payload.get("metadata") or {}

        logger.info(
            "saving_answer user_id=%s category=%s subject=%s score=%s",
            user.get("_id"),
            payload["category"],
            payload["subject"],
            score,
        )

        answer_id = self.questions_repository.add_question(
            user_id=user["_id"],
            username=user.get("username", user.get("email", "anonymous")),
            question_text=payload["question"],
            keyword=keyword,
            category=payload["category"],
            subject=payload["subject"],
            difficulty=difficulty,
            ai_generated=True,
            extra={
                "user_answer": answer_text,
                "score": score,
                "evaluation": evaluation,
                "metadata": metadata,
            },
        )

        self.user_repository.add_experience(
            user.get("username", user.get("email", "")), score or 0
        )

        logger.info(
            "answer_saved answer_id=%s user_id=%s score=%s",
            answer_id,
            user.get("_id"),
            score,
        )

        return answer_id

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get top 10 users leaderboard."""
        logger.info("fetching_leaderboard")

        top_ten = self.leaderboard_repository.get_top_ten()

        logger.info("leaderboard_fetched count=%d", len(top_ten))

        return top_ten

    def update_leaderboard_entry(self, user_id: str, username: str) -> Dict[str, Any]:
        """
        Update leaderboard entry for a user based on their performance.

        Args:
            user_id: User's ID
            username: User's username

        Returns:
            Dictionary with update status and average score

        Raises:
            ValueError: If user not found
        """
        logger.info("updating_leaderboard user_id=%s username=%s", user_id, username)

        # Get user's exp and question count
        user = self.user_repository.get_user_by_username(username)
        if not user:
            logger.warning("user_not_found username=%s", username)
            raise ValueError("User not found")

        exp = user.get("experience", 0)
        count = user.get("questions_count", 1)  # Default to 1 to avoid division by zero

        # Calculate average score: exp / count
        avg_score = exp / count if count > 0 else 0

        # Update leaderboard with calculated average
        self.leaderboard_repository.add_or_update_entry(
            username=username,
            score=avg_score,
            meta={"exp": exp, "count": count},
        )

        logger.info(
            "leaderboard_entry_updated username=%s avg_score=%.2f exp=%d count=%d",
            username,
            avg_score,
            exp,
            count,
        )

        return {"status": "updated", "avg_score": avg_score}

    def get_user_history(
        self,
        authenticated_user: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 20,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return a user's saved answer history formatted for UI consumption."""

        user = self._resolve_user(authenticated_user, user_id=user_id, email=email)
        raw_entries = self.questions_repository.get_questions_by_user(
            user_id=user["_id"], limit=limit, before=before
        )

        history: List[Dict[str, Any]] = []
        for entry in raw_entries:
            extra = entry.get("extra", {}) or {}
            created_at = entry.get("created_at")
            
            # Properly handle datetime conversion
            if isinstance(created_at, datetime):
                created_iso = created_at.isoformat()
            elif isinstance(created_at, str):
                created_iso = created_at
            else:
                created_iso = datetime.now().isoformat()
            
            history.append(
                {
                    "id": entry.get("_id"),
                    "summary": {
                        "category": entry.get("category"),
                        "subject": entry.get("subject"),
                        "difficulty": entry.get("difficulty"),
                        "score": extra.get("score"),
                        "keyword": entry.get("keyword"),
                        "created_at": created_iso,
                    },
                    "details": {
                        "question": entry.get("question_text"),
                        "answer": extra.get("user_answer"),
                        "evaluation": extra.get("evaluation"),
                        "metadata": extra.get("metadata"),
                    },
                }
            )

        logger.info(
            "history_fetched user_id=%s count=%d",
            user.get("_id"),
            len(history),
        )
        return history

    def _resolve_user(
        self,
        authenticated_user: Optional[Dict[str, Any]],
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        if authenticated_user:
            return authenticated_user

        lookups = (
            (user_id, self.user_repository.get_user_by_id),
            (username, self.user_repository.get_user_by_username),
            (email, self.user_repository.get_user_by_email),
        )

        for value, resolver in lookups:
            if value:
                user = resolver(value)
                if user:
                    return user

        raise ValueError("Unable to resolve user context for answer recording")

    @staticmethod
    def _normalize_score(score_value: Any, evaluation: Optional[Dict[str, Any]]) -> Optional[int]:
        if isinstance(score_value, (int, float)):
            return int(score_value)

        if isinstance(score_value, str):
            match = re.search(r"(\d+)", score_value)
            if match:
                return int(match.group(1))

        if evaluation:
            evaluation_score = evaluation.get("score")
            if isinstance(evaluation_score, (int, float)):
                return int(evaluation_score)
            if isinstance(evaluation_score, str):
                match = re.search(r"(\d+)", evaluation_score)
                if match:
                    return int(match.group(1))

        return None

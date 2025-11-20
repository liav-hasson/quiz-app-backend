"""User activity controller for tracking answers and leaderboard."""

import logging
from typing import Dict, Any, List, Tuple
from utils.validation import validate_difficulty, validate_required_fields

logger = logging.getLogger(__name__)


class UserActivityController:
    """Controller for user activity tracking (answers, leaderboard)."""

    def __init__(self, user_controller, questions_controller, toptens_controller):
        """Initialize with database controller dependencies."""
        self.user_controller = user_controller
        self.questions_controller = questions_controller
        self.toptens_controller = toptens_controller

    def handle_save_answer(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to save user's answer.

        Args:
            data: Request JSON data

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            validate_required_fields(
                data,
                [
                    "user_id",
                    "username",
                    "question",
                    "answer",
                    "difficulty",
                    "category",
                    "subject",
                ],
            )
            difficulty = validate_difficulty(data["difficulty"])
        except ValueError as e:
            logger.warning("save_answer_validation_failed error=%s", str(e))
            return {"error": str(e)}, 400

        try:
            answer_id = self.save_user_answer(
                user_id=data["user_id"],
                username=data["username"],
                question=data["question"],
                answer=data["answer"],
                difficulty=difficulty,
                category=data["category"],
                subject=data["subject"],
                keyword=data.get("keyword", ""),
                score=data.get("score", 0),
            )

            return {"answer_id": answer_id}, 201

        except Exception as e:
            logger.error("answer_save_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to save answer: {str(e)}"}, 500

    def handle_get_leaderboard(self) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to get leaderboard.

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            leaderboard = self.get_leaderboard()
            return {"leaderboard": leaderboard, "count": len(leaderboard)}, 200
        except Exception as e:
            logger.error("leaderboard_fetch_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to fetch leaderboard: {str(e)}"}, 500

    def handle_update_leaderboard(
        self, data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to update leaderboard entry.

        Args:
            data: Request JSON data

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            validate_required_fields(data, ["user_id", "username"])
        except ValueError as e:
            logger.warning("leaderboard_update_validation_failed error=%s", str(e))
            return {"error": str(e)}, 400

        try:
            result = self.update_leaderboard_entry(
                user_id=data["user_id"], username=data["username"]
            )
            return result, 201

        except ValueError as e:
            logger.warning("user_not_found username=%s", data.get("username"))
            return {"error": str(e)}, 404
        except Exception as e:
            logger.error("leaderboard_update_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to update leaderboard: {str(e)}"}, 500

    def save_user_answer(
        self,
        user_id: str,
        username: str,
        question: str,
        answer: str,
        difficulty: int,
        category: str,
        subject: str,
        keyword: str = "",
        score: int = 0,
    ) -> str:
        """
        Save a user's answer and update their statistics.

        Args:
            user_id: User's ID
            username: User's username
            question: Question text
            answer: User's answer
            difficulty: Difficulty level
            category: Quiz category
            subject: Quiz subject
            keyword: Question keyword
            is_correct: Whether answer was correct (optional)
            score: Points earned

        Returns:
            Answer ID
        """
        logger.info(
            "saving_answer user_id=%s category=%s subject=%s score=%d",
            user_id,
            category,
            subject,
            score,
        )

        # Save the answer record
        answer_id = self.questions_controller.add_question(
            user_id=user_id,
            username=username,
            question_text=question,
            keyword=keyword,
            category=category,
            subject=subject,
            difficulty=difficulty,
            ai_generated=True,
            extra={
                "user_answer": answer,
                "score": score,
            },
        )

        # Update user's exp (accumulated score)
        self.user_controller.add_experience(username, score)

        logger.info(
            "answer_saved answer_id=%s user_id=%s score=%d", answer_id, user_id, score
        )

        return answer_id

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get top 10 users leaderboard."""
        logger.info("fetching_leaderboard")

        top_ten = self.toptens_controller.get_top_ten()

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
        user = self.user_controller.get_user_by_username(username)
        if not user:
            logger.warning("user_not_found username=%s", username)
            raise ValueError("User not found")

        exp = user.get("experience", 0)
        count = user.get("questions_count", 1)  # Default to 1 to avoid division by zero

        # Calculate average score: exp / count
        avg_score = exp / count if count > 0 else 0

        # Update leaderboard with calculated average
        self.toptens_controller.add_or_update_entry(
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

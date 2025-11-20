"""Quiz controller for handling quiz-related business logic."""

import logging
from typing import Dict, Any, List, Optional, Tuple
from utils.quiz_utils import (
    get_categories,
    get_subjects,
    get_all_subjects,
    get_random_keyword,
    get_random_style_modifier,
)
from utils.ai_utils import generate_question, evaluate_answer
from utils.validation import validate_difficulty, validate_required_fields

logger = logging.getLogger(__name__)


class QuizController:
    """Controller for quiz operations."""

    @staticmethod
    def handle_get_categories() -> Tuple[Dict[str, Any], int]:
        """
        Handle request to get all categories.

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            logger.info("fetching_all_categories")
            categories = get_categories()
            logger.info("categories_fetched count=%d", len(categories))
            return {"categories": categories}, 200
        except Exception as e:
            logger.error("categories_fetch_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to get categories: {str(e)}"}, 500

    @staticmethod
    def handle_get_subjects(category: Optional[str]) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to get subjects for a category.

        Args:
            category: Category name from query params

        Returns:
            Tuple of (response_data, status_code)
        """
        if not category:
            logger.warning("subjects_request_missing_category")
            return {"error": "category parameter required"}, 400

        try:
            logger.info("fetching_subjects category=%s", category)
            subjects = get_subjects(category)
            logger.info(
                "subjects_fetched category=%s count=%d", category, len(subjects)
            )
            return {"subjects": subjects}, 200
        except Exception as e:
            logger.error(
                "subjects_fetch_failed category=%s error=%s",
                category,
                str(e),
                exc_info=True,
            )
            return {"error": f"Failed to get subjects: {str(e)}"}, 500

    @staticmethod
    def handle_get_all_subjects() -> Tuple[Dict[str, Any], int]:
        """
        Handle request to get all subjects for all categories.

        This combined endpoint reduces API calls by returning all subjects
        for all categories in a single response.

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            logger.info("fetching_all_subjects")
            data = get_all_subjects()
            total_subjects = sum(len(subjects) for subjects in data.values())
            logger.info(
                "all_subjects_fetched category_count=%d total_subjects=%d",
                len(data),
                total_subjects,
            )
            return {"data": data}, 200
        except Exception as e:
            logger.error("all_subjects_fetch_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to get all subjects: {str(e)}"}, 500

    @staticmethod
    def handle_generate_question(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to generate a quiz question.

        Args:
            data: Request JSON data

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            validate_required_fields(data, ["category", "subject", "difficulty"])
            difficulty = validate_difficulty(data["difficulty"])
        except ValueError as e:
            logger.warning("generate_question_validation_failed error=%s", str(e))
            return {"error": str(e)}, 400

        try:
            question_data = QuizController.generate_quiz_question(
                category=data["category"],
                subject=data["subject"],
                difficulty=difficulty,
            )
            return question_data, 200
        except ValueError as e:
            return {"error": str(e)}, 404
        except Exception as e:
            logger.error(
                "question_generation_failed category=%s subject=%s error=%s",
                data["category"],
                data["subject"],
                str(e),
                exc_info=True,
            )
            return {"error": f"Failed to generate question: {str(e)}"}, 500

    @staticmethod
    def handle_evaluate_answer(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Handle request to evaluate an answer.

        Args:
            data: Request JSON data

        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            validate_required_fields(data, ["question", "answer", "difficulty"])
            difficulty = validate_difficulty(data["difficulty"])
        except ValueError as e:
            logger.warning("evaluate_answer_validation_failed error=%s", str(e))
            return {"error": str(e)}, 400

        try:
            evaluation = QuizController.evaluate_user_answer(
                question=data["question"], answer=data["answer"], difficulty=difficulty
            )
            # evaluation is now a dict with {score, feedback}
            return evaluation, 200
        except Exception as e:
            logger.error("answer_evaluation_failed error=%s", str(e), exc_info=True)
            return {"error": f"Failed to evaluate answer: {str(e)}"}, 500

    @staticmethod
    def get_all_categories() -> List[str]:
        """Get all available quiz categories."""
        logger.info("fetching_all_categories")
        categories = get_categories()
        logger.info("categories_fetched count=%d", len(categories))
        return categories

    @staticmethod
    def get_subjects_for_category(category: str) -> List[str]:
        """Get subjects for a given category."""
        logger.info("fetching_subjects category=%s", category)
        subjects = get_subjects(category)
        logger.info("subjects_fetched category=%s count=%d", category, len(subjects))
        return subjects

    @staticmethod
    def generate_quiz_question(
        category: str, subject: str, difficulty: int
    ) -> Dict[str, Any]:
        """
        Generate a quiz question.

        Args:
            category: Quiz category
            subject: Quiz subject
            difficulty: Difficulty level (1-3)

        Returns:
            Dictionary containing question data

        Raises:
            ValueError: If no keywords found for category/subject
        """
        logger.info(
            "generating_question category=%s subject=%s difficulty=%d",
            category,
            subject,
            difficulty,
        )

        keyword = get_random_keyword(category, subject)
        if not keyword:
            logger.warning(
                "no_keywords_found category=%s subject=%s", category, subject
            )
            raise ValueError("No keywords found for this category and subject")

        # Get random style modifier
        style_modifier = get_random_style_modifier(category, subject)

        question = generate_question(
            category, subject, keyword, difficulty, style_modifier
        )

        logger.info(
            "question_generated category=%s subject=%s difficulty=%d keyword=%s style_modifier=%s",
            category,
            subject,
            difficulty,
            keyword,
            style_modifier,
        )

        return {
            "question": question,
            "keyword": keyword,
            "category": category,
            "subject": subject,
            "difficulty": difficulty,
        }

    @staticmethod
    def evaluate_user_answer(question: str, answer: str, difficulty: int) -> Dict[str, Any]:
        """
        Evaluate a user's answer to a question.

        Args:
            question: The question that was asked
            answer: User's answer
            difficulty: Difficulty level (1-3)

        Returns:
            Dict with score and feedback: {"score": "8/10", "feedback": "..."}
        """
        logger.info(
            "evaluating_answer difficulty=%d answer_length=%d", difficulty, len(answer)
        )

        evaluation = evaluate_answer(question, answer, difficulty)

        logger.info(
            "answer_evaluated difficulty=%d score=%s",
            difficulty,
            evaluation.get("score", "N/A"),
        )

        return evaluation

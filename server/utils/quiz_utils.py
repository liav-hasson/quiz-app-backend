"""Quiz utilities for managing quiz data and operations.

This module provides a service layer for quiz operations including:
- Category and subject management
- Keyword retrieval and search
- Quiz question generation
- MongoDB integration through QuizController

The module maintains a global QuizService instance for backward compatibility
with existing function-based interfaces.
"""

import logging
import random
from typing import List, Optional

from models.dbcontroller import DBController
from models.quiz_controller import QuizController

logger = logging.getLogger(__name__)


class QuizService:
    """Service class to handle quiz operations using MongoDB.

    Provides methods for:
    - Fetching categories, subjects, and keywords
    - Generating random quiz questions
    - Searching keywords
    - Managing MongoDB connections
    """

    def __init__(self) -> None:
        """Initialize QuizService with MongoDB connection."""
        self._db_controller: Optional[DBController] = None
        self._quiz_controller: Optional[QuizController] = None
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize MongoDB connection and controllers."""
        try:
            logger.info("initializing_mongodb_connection")
            self._db_controller = DBController()
            if self._db_controller.connect():
                self._quiz_controller = QuizController(self._db_controller)
                logger.info("mongodb_connection_successful")
            else:
                raise ConnectionError("Failed to connect to MongoDB")
        except Exception as exc:
            logger.error("mongodb_connection_failed error=%s", str(exc))
            print(f"Warning: MongoDB connection failed: {exc}")
            print("Quiz functions will not work until database is available.")
            self._quiz_controller = None

    def _ensure_connection(self) -> QuizController:
        """Ensure we have a valid connection.

        Returns:
            QuizController: Active quiz controller instance.

        Raises:
            ConnectionError: If no database connection available.
        """
        if not self._quiz_controller:
            logger.error("no_database_connection_available")
            raise ConnectionError(
                "No database connection available. "
                "Please check MongoDB is running on localhost:27017"
            )
        return self._quiz_controller

    def get_categories(self) -> List[str]:
        """Return a list of all categories (topics).

        Returns:
            List[str]: List of category names.
        """
        logger.debug("fetching_categories")
        quiz_controller = self._ensure_connection()
        categories = quiz_controller.get_all_topics()
        logger.debug("categories_fetched count=%d", len(categories))
        return categories

    def get_subjects(self, category: str) -> List[str]:
        """Return a list of subjects (subtopics) for a given category.

        Args:
            category: Category name.

        Returns:
            List[str]: List of subject names.
        """
        logger.debug("fetching_subjects category=%s", category)
        quiz_controller = self._ensure_connection()
        subjects = quiz_controller.get_subtopics_by_topic(category)
        logger.debug("subjects_fetched category=%s count=%d", category, len(subjects))
        return subjects

    def get_keywords(self, category: str, subject: str) -> List[str]:
        """Return all keywords for a given category and subject.

        Args:
            category: Category name.
            subject: Subject name.

        Returns:
            List[str]: List of keywords.
        """
        quiz_controller = self._ensure_connection()
        return quiz_controller.get_keywords_by_topic_subtopic(category, subject)

    def get_random_keyword(self, category: str, subject: str) -> Optional[str]:
        """Return a random keyword for a given category and subject.

        Args:
            category: Category name.
            subject: Subject name.

        Returns:
            Optional[str]: Random keyword or None if no keywords available.
        """
        logger.debug(
            "fetching_random_keyword category=%s subject=%s", category, subject
        )
        quiz_controller = self._ensure_connection()
        keywords = quiz_controller.get_keywords_by_topic_subtopic(category, subject)
        keyword = random.choice(keywords) if keywords else None
        if keyword:
            logger.debug("random_keyword_selected keyword=%s", keyword)
        else:
            logger.warning(
                "no_keywords_available category=%s subject=%s", category, subject
            )
        return keyword

    def get_random_style_modifier(self, category: str, subject: str) -> Optional[str]:
        """Return a random style modifier for a given category and subject.

        Args:
            category: Category name.
            subject: Subject name.

        Returns:
            Optional[str]: Random style modifier or None if none available.
        """
        logger.debug(
            "fetching_random_style_modifier category=%s subject=%s", category, subject
        )
        quiz_controller = self._ensure_connection()
        style_modifiers = quiz_controller.get_style_modifiers_by_topic_subtopic(
            category, subject
        )

        # Check if list has items (empty list [] is truthy but has no items)
        if style_modifiers and len(style_modifiers) > 0:
            style_modifier = random.choice(style_modifiers)
            logger.debug(
                "random_style_modifier_selected style_modifier=%s", style_modifier
            )
            return style_modifier

        logger.warning(
            "no_style_modifiers_available category=%s subject=%s", category, subject
        )
        return None

    def get_random_keywords_from_category(
        self, category: str, count: int = 1
    ) -> List[str]:
        """Get random keywords from any subject within a category.

        Args:
            category: Category name.
            count: Number of keywords to return (default: 1).

        Returns:
            List[str]: List of random keywords.
        """
        quiz_controller = self._ensure_connection()
        all_keywords = quiz_controller.get_all_keywords_by_topic(category)
        if not all_keywords:
            return []

        # If we want more keywords than available, return all
        if count >= len(all_keywords):
            return all_keywords

        return random.sample(all_keywords, count)

    def get_quiz_questions(
        self, category: Optional[str] = None, count: int = 10
    ) -> List[dict]:
        """Generate quiz questions with random keywords.

        Args:
            category: Specific category to focus on (optional).
            count: Number of questions to generate (default: 10).

        Returns:
            List[dict]: List of dictionaries with question data.
        """
        quiz_controller = self._ensure_connection()
        random_items = quiz_controller.get_random_keywords(category, count)

        questions = []
        for item in random_items:
            questions.append(
                {
                    "keyword": item["keyword"],
                    "topic": item["topic"],
                    "subtopic": item["subtopic"],
                    "question_id": item["_id"],
                }
            )

        return questions

    def search_keywords(self, search_term: str) -> List[dict]:
        """Search for keywords containing the search term.

        Args:
            search_term: Term to search for in keywords.

        Returns:
            List[dict]: List of matching documents.
        """
        quiz_controller = self._ensure_connection()
        return quiz_controller.search_keywords(search_term)

    def disconnect(self) -> None:
        """Clean up database connection."""
        if self._db_controller:
            self._db_controller.disconnect()


# Global instance for backward compatibility
_quiz_service = QuizService()


def get_categories() -> List[str]:
    """Return a list of all categories.

    Returns:
        List[str]: List of category names.
    """
    return _quiz_service.get_categories()


def get_subjects(category: str) -> List[str]:
    """Return a list of subjects for a given category.

    Args:
        category: Category name.

    Returns:
        List[str]: List of subject names.
    """
    return _quiz_service.get_subjects(category)


def get_random_keyword(category: str, subject: str) -> Optional[str]:
    """Return a random keyword for a given category and subject.

    Args:
        category: Category name.
        subject: Subject name.

    Returns:
        Optional[str]: Random keyword or None.
    """
    return _quiz_service.get_random_keyword(category, subject)


def get_random_style_modifier(category: str, subject: str) -> Optional[str]:
    """Return a random style modifier for a given category and subject.

    Args:
        category: Category name.
        subject: Subject name.

    Returns:
        Optional[str]: Random style modifier or None.
    """
    return _quiz_service.get_random_style_modifier(category, subject)


def get_keywords(category: str, subject: str) -> List[str]:
    """Return all keywords for a given category and subject.

    Args:
        category: Category name.
        subject: Subject name.

    Returns:
        List[str]: List of keywords.
    """
    return _quiz_service.get_keywords(category, subject)


def get_random_keywords_from_category(category: str, count: int = 1) -> List[str]:
    """Get random keywords from any subject within a category.

    Args:
        category: Category name.
        count: Number of keywords to return (default: 1).

    Returns:
        List[str]: List of random keywords.
    """
    return _quiz_service.get_random_keywords_from_category(category, count)


def get_quiz_questions(category: Optional[str] = None, count: int = 10) -> List[dict]:
    """Generate quiz questions with random keywords.

    Args:
        category: Optional category to filter by.
        count: Number of questions to generate (default: 10).

    Returns:
        List[dict]: List of question dictionaries.
    """
    return _quiz_service.get_quiz_questions(category, count)


def search_keywords(search_term: str) -> List[dict]:
    """Search for keywords containing the search term.

    Args:
        search_term: Term to search for.

    Returns:
        List[dict]: List of matching documents.
    """
    return _quiz_service.search_keywords(search_term)


def cleanup() -> None:
    """Clean up database connections."""
    _quiz_service.disconnect()


# Example usage and testing
if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=broad-exception-caught
    try:
        print("Testing MongoDB-based quiz utils...")

        # Test basic functions
        categories = get_categories()
        print(f"Available categories: {categories}")

        if categories:
            first_category = categories[0]
            subjects = get_subjects(first_category)
            print(f"Subjects in '{first_category}': {subjects}")

            if subjects:
                first_subject = subjects[0]
                keyword = get_random_keyword(first_category, first_subject)
                print(
                    f"Random keyword from '{first_category}' -> "
                    f"'{first_subject}': {keyword}"
                )

                # Get multiple keywords
                keywords = get_keywords(first_category, first_subject)
                print(f"All keywords in '{first_subject}': {len(keywords)} total")

                # Generate quiz questions
                quiz = get_quiz_questions(first_category, 3)
                print(f"Sample quiz questions from '{first_category}':")
                for i, question in enumerate(quiz, 1):
                    print(f"  {i}. {question['keyword']} (from {question['subtopic']})")

        # Test search
        search_results = search_keywords("docker")
        print(f"Search results for 'docker': {len(search_results)} matches")

    except Exception as exc:
        print(f"Error testing quiz utils: {exc}")
        print("Make sure MongoDB is running and the quiz data has been migrated.")

    finally:
        cleanup()

import random
import sys
import os
import logging
from typing import List, Optional

# Add the db directory to the path so we can import our controllers
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "db"))

from dbcontroller import DBController, QuizController

logger = logging.getLogger(__name__)


class QuizService:
    """Service class to handle quiz operations using MongoDB"""

    def __init__(self):
        self._db_controller = None
        self._quiz_controller = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize MongoDB connection and controllers"""
        try:
            logger.info("initializing_mongodb_connection")
            self._db_controller = DBController()
            if self._db_controller.connect():
                self._quiz_controller = QuizController(self._db_controller)
                logger.info("mongodb_connection_successful")
            else:
                raise Exception("Failed to connect to MongoDB")
        except Exception as e:
            logger.error("mongodb_connection_failed error=%s", str(e))
            print(f"Warning: MongoDB connection failed: {e}")
            print("Quiz functions will not work until database is available.")
            self._quiz_controller = None

    def _ensure_connection(self):
        """Ensure we have a valid connection"""
        if not self._quiz_controller:
            logger.error("no_database_connection_available")
            raise Exception(
                "No database connection available. Please check MongoDB is running on localhost:27017"
            )
        return self._quiz_controller

    def get_categories(self) -> List[str]:
        """Return a list of all categories (topics)."""
        logger.debug("fetching_categories")
        quiz_controller = self._ensure_connection()
        categories = quiz_controller.get_all_topics()
        logger.debug("categories_fetched count=%d", len(categories))
        return categories

    def get_subjects(self, category: str) -> List[str]:
        """Return a list of subjects (subtopics) for a given category."""
        logger.debug("fetching_subjects category=%s", category)
        quiz_controller = self._ensure_connection()
        subjects = quiz_controller.get_subtopics_by_topic(category)
        logger.debug("subjects_fetched category=%s count=%d", category, len(subjects))
        return subjects

    def get_keywords(self, category: str, subject: str) -> List[str]:
        """Return all keywords for a given category and subject."""
        quiz_controller = self._ensure_connection()
        return quiz_controller.get_keywords_by_topic_subtopic(category, subject)

    def get_random_keyword(self, category: str, subject: str) -> Optional[str]:
        """Return a random keyword for a given category and subject."""
        logger.debug("fetching_random_keyword category=%s subject=%s", category, subject)
        quiz_controller = self._ensure_connection()
        keywords = quiz_controller.get_keywords_by_topic_subtopic(category, subject)
        keyword = random.choice(keywords) if keywords else None
        if keyword:
            logger.debug("random_keyword_selected keyword=%s", keyword)
        else:
            logger.warning("no_keywords_available category=%s subject=%s", category, subject)
        return keyword

    def get_random_keywords_from_category(
        self, category: str, count: int = 1
    ) -> List[str]:
        """Get random keywords from any subject within a category."""
        quiz_controller = self._ensure_connection()
        all_keywords = quiz_controller.get_all_keywords_by_topic(category)
        if not all_keywords:
            return []

        # If we want more keywords than available, return all
        if count >= len(all_keywords):
            return all_keywords

        return random.sample(all_keywords, count)

    def get_quiz_questions(self, category: str = None, count: int = 10) -> List[dict]:
        """
        Generate quiz questions with random keywords.

        Args:
            category: Specific category to focus on (optional)
            count: Number of questions to generate

        Returns:
            List of dictionaries with question data
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
        """Search for keywords containing the search term."""
        quiz_controller = self._ensure_connection()
        return quiz_controller.search_keywords(search_term)

    def disconnect(self):
        """Clean up database connection"""
        if self._db_controller:
            self._db_controller.disconnect()


# Global instance for backward compatibility
_quiz_service = QuizService()


# Backward-compatible function interface
def get_categories() -> List[str]:
    """Return a list of all categories."""
    return _quiz_service.get_categories()


def get_subjects(category: str) -> List[str]:
    """Return a list of subjects for a given category."""
    return _quiz_service.get_subjects(category)


def get_random_keyword(category: str, subject: str) -> Optional[str]:
    """Return a random keyword for a given category and subject."""
    return _quiz_service.get_random_keyword(category, subject)


def get_keywords(category: str, subject: str) -> List[str]:
    """Return all keywords for a given category and subject."""
    return _quiz_service.get_keywords(category, subject)


def get_random_keywords_from_category(category: str, count: int = 1) -> List[str]:
    """Get random keywords from any subject within a category."""
    return _quiz_service.get_random_keywords_from_category(category, count)


def get_quiz_questions(category: str = None, count: int = 10) -> List[dict]:
    """Generate quiz questions with random keywords."""
    return _quiz_service.get_quiz_questions(category, count)


def search_keywords(search_term: str) -> List[dict]:
    """Search for keywords containing the search term."""
    return _quiz_service.search_keywords(search_term)


# Cleanup function for when module is unloaded
def cleanup():
    """Clean up database connections"""
    _quiz_service.disconnect()


# Example usage and testing
if __name__ == "__main__":
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
                    f"Random keyword from '{first_category}' -> '{first_subject}': {keyword}"
                )

                # Get multiple keywords
                keywords = get_keywords(first_category, first_subject)
                print(f"All keywords in '{first_subject}': {len(keywords)} total")

                # Generate quiz questions
                quiz = get_quiz_questions(first_category, 3)
                print(f"Sample quiz questions from '{first_category}':")
                for i, q in enumerate(quiz, 1):
                    print(f"  {i}. {q['keyword']} (from {q['subtopic']})")

        # Test search
        search_results = search_keywords("docker")
        print(f"Search results for 'docker': {len(search_results)} matches")

    except Exception as e:
        print(f"Error testing quiz utils: {e}")
        print("Make sure MongoDB is running and the quiz data has been migrated.")

    finally:
        cleanup()

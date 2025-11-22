"""Quiz controller for managing quiz catalog and keyword logic."""

import logging
import random
from typing import Dict, List, Optional, Any

from models.repositories.quiz_repository import QuizRepository

logger = logging.getLogger(__name__)


class QuizController:
    """Orchestrates quiz metadata queries via the repository layer."""

    def __init__(self, quiz_repository: QuizRepository) -> None:
        """Initialize QuizController.
        
        Args:
            quiz_repository: Repository for accessing quiz data (categories, subjects, keywords)
        """
        self._quiz_repository = quiz_repository

    def get_categories(self) -> List[str]:
        """Return a list of all categories (topics)."""

        logger.debug("fetching_categories")
        categories = self._quiz_repository.get_all_topics()
        logger.debug("categories_fetched count=%d", len(categories))
        return categories

    def get_subjects(self, category: str) -> List[str]:
        """Return all subjects for a given category."""

        logger.debug("fetching_subjects category=%s", category)
        subjects = self._quiz_repository.get_subtopics_by_topic(category)
        logger.debug("subjects_fetched category=%s count=%d", category, len(subjects))
        return subjects

    def get_all_subjects(self) -> Dict[str, List[str]]:
        """Return all subjects for every category."""

        logger.debug("fetching_all_subjects")
        categories = self._quiz_repository.get_all_topics()

        result: Dict[str, List[str]] = {}
        for category in categories:
            result[category] = self._quiz_repository.get_subtopics_by_topic(category)

        logger.debug(
            "all_subjects_fetched category_count=%d total_subjects=%d",
            len(result),
            sum(len(subjects) for subjects in result.values()),
        )
        return result

    def get_keywords(self, category: str, subject: str) -> List[str]:
        """Return all keywords for a specific category & subject."""

        return self._quiz_repository.get_keywords_by_topic_subtopic(category, subject)

    def get_random_keyword(self, category: str, subject: str) -> Optional[str]:
        """Return a random keyword for a category and subject."""

        logger.debug(
            "fetching_random_keyword category=%s subject=%s", category, subject
        )
        keywords = self._quiz_repository.get_keywords_by_topic_subtopic(
            category, subject
        )
        keyword = random.choice(keywords) if keywords else None
        if keyword:
            logger.debug("random_keyword_selected keyword=%s", keyword)
        else:
            logger.warning(
                "no_keywords_available category=%s subject=%s", category, subject
            )
        return keyword

    def get_random_style_modifier(self, category: str, subject: str) -> Optional[str]:
        """Return a random style modifier for a category and subject."""

        logger.debug(
            "fetching_random_style_modifier category=%s subject=%s", category, subject
        )
        style_modifiers = self._quiz_repository.get_style_modifiers_by_topic_subtopic(
            category, subject
        )

        if style_modifiers:
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
        """Return random keywords across subjects for a category."""

        all_keywords = self._quiz_repository.get_all_keywords_by_topic(category)
        if not all_keywords:
            return []
        if count >= len(all_keywords):
            return all_keywords
        return random.sample(all_keywords, count)

    def get_quiz_questions(
        self, category: Optional[str] = None, count: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate quiz question payloads using random keywords."""

        random_items = self._quiz_repository.get_random_keywords(category, count)
        questions: List[Dict[str, Any]] = []
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

    def search_keywords(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for keywords containing the search term."""

        return self._quiz_repository.search_keywords(search_term)

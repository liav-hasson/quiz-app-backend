"""Tests for quiz controller module."""

from controllers.quiz_controller import QuizController


class DummyQuizRepository:
    """In-memory quiz data used to drive deterministic controller tests."""

    def __init__(self) -> None:
        self._data = {
            "Containers": {
                "Basics": {
                    "keywords": ["Docker", "Podman"],
                    "style_modifiers": ["concept explanation"],
                },
                "Advanced": {
                    "keywords": ["Kubernetes"],
                    "style_modifiers": ["comparison"],
                },
            },
            "CI/CD": {
                "Basics": {
                    "keywords": ["Pipelines"],
                    "style_modifiers": ["use case scenario"],
                }
            },
        }

    def get_all_topics(self):
        return list(self._data.keys())

    def get_subtopics_by_topic(self, topic: str):
        return list(self._data.get(topic, {}).keys())

    def get_keywords_by_topic_subtopic(self, topic: str, subtopic: str):
        return self._data.get(topic, {}).get(subtopic, {}).get("keywords", [])

    def get_style_modifiers_by_topic_subtopic(self, topic: str, subtopic: str):
        return self._data.get(topic, {}).get(subtopic, {}).get("style_modifiers", [])


_controller = QuizController(DummyQuizRepository())


def test_get_categories():
    """Categories should be a non-empty list."""
    categories = _controller.get_categories()
    assert len(categories) > 0


def test_get_subjects_valid():
    """Valid category should return subjects."""
    subjects = _controller.get_subjects("Containers")
    assert len(subjects) > 0


def test_get_subjects_invalid():
    """Invalid category should return empty list."""
    assert _controller.get_subjects("Invalid") == []


def test_get_random_keyword_valid():
    """Valid category and subject should return a keyword."""
    keyword = _controller.get_random_keyword("Containers", "Basics")
    assert keyword is not None


def test_get_random_keyword_invalid():
    """Invalid inputs should return None."""
    assert _controller.get_random_keyword("Invalid", "Invalid") is None

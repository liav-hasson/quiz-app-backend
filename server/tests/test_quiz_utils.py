"""Tests for quiz_utils module."""
from utils.quiz_utils import get_categories, get_subjects, get_random_keyword


def test_get_categories():
    """Categories should be a non-empty list."""
    categories = get_categories()
    assert len(categories) > 0


def test_get_subjects_valid():
    """Valid category should return subjects."""
    subjects = get_subjects("Containers")
    assert len(subjects) > 0


def test_get_subjects_invalid():
    """Invalid category should return empty list."""
    assert get_subjects("Invalid") == []


def test_get_random_keyword_valid():
    """Valid category and subject should return a keyword."""
    keyword = get_random_keyword("Containers", "Basics")
    assert keyword is not None


def test_get_random_keyword_invalid():
    """Invalid inputs should return None."""
    assert get_random_keyword("Invalid", "Invalid") is None

"""Reusable request validation helpers."""

import logging
from typing import Iterable, Mapping

logger = logging.getLogger(__name__)

# Difficulty level constants
DIFFICULTY_EASY = 1
DIFFICULTY_MEDIUM = 2
DIFFICULTY_HARD = 3
VALID_DIFFICULTIES = (DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD)

# History limit constants
MIN_HISTORY_LIMIT = 1
MAX_HISTORY_LIMIT = 100
DEFAULT_HISTORY_LIMIT = 20


def validate_difficulty(difficulty):
    """Validate difficulty level is 1, 2, or 3."""

    try:
        difficulty = int(difficulty)
        if difficulty not in VALID_DIFFICULTIES:
            logger.warning("invalid_difficulty_value value=%s", difficulty)
            raise ValueError(f"Difficulty must be one of {VALID_DIFFICULTIES}")
        return difficulty
    except (TypeError, ValueError) as exc:
        logger.warning("difficulty_validation_failed value=%s", difficulty)
        raise ValueError(f"Invalid difficulty: {difficulty}") from exc


def validate_required_fields(data: Mapping[str, object], required_fields: Iterable[str]):
    """Ensure all required_fields exist (truthy) in data."""

    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        logger.warning("missing_required_fields fields=%s", ", ".join(missing))
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return data

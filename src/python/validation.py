"""Input validation utilities for the quiz API."""
import logging

logger = logging.getLogger(__name__)


def validate_difficulty(difficulty):
    """Validate difficulty level is 1, 2, or 3.
    
    Args:
        difficulty: The difficulty value to validate (any type).
        
    Returns:
        int: The validated difficulty (1-3).
        
    Raises:
        ValueError: If difficulty is invalid.
    """
    try:
        difficulty = int(difficulty)
        if difficulty not in [1, 2, 3]:
            logger.warning("invalid_difficulty_value value=%s", difficulty)
            raise ValueError("Difficulty must be 1, 2, or 3")
        return difficulty
    except (TypeError, ValueError) as exc:
        logger.warning("difficulty_validation_failed value=%s", difficulty)
        raise ValueError(f"Invalid difficulty: {difficulty}") from exc


def validate_required_fields(data, required_fields):
    """Validate that all required fields are present in data.
    
    Args:
        data: Dictionary to validate.
        required_fields: List of required field names.
        
    Returns:
        dict: The validated data.
        
    Raises:
        ValueError: If any required field is missing.
    """
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        logger.warning("missing_required_fields fields=%s", ', '.join(missing))
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return data

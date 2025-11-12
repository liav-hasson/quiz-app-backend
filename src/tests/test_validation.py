"""Tests for validation module."""
import pytest
from validation import validate_difficulty, validate_required_fields


def test_validate_difficulty():
    """Valid difficulty levels should pass."""
    assert validate_difficulty(1) == 1
    assert validate_difficulty("2") == 2


def test_validate_difficulty_invalid():
    """Invalid difficulty should raise ValueError."""
    with pytest.raises(ValueError):
        validate_difficulty(0)
    with pytest.raises(ValueError):
        validate_difficulty(4)


def test_validate_required_fields():
    """All required fields present should pass."""
    data = {"name": "test", "value": "123"}
    assert validate_required_fields(data, ["name", "value"]) == data


def test_validate_required_fields_missing():
    """Missing required field should raise ValueError."""
    with pytest.raises(ValueError):
        validate_required_fields({"name": "test"}, ["name", "value"])

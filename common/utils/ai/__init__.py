"""AI utilities package exposing a default question service."""

from __future__ import annotations

from .provider import OpenAIProvider
from .prompts import QUESTION_PROMPTS, EVAL_PROMPT
from .service import AIQuestionService

_default_service = AIQuestionService()


def get_service() -> AIQuestionService:
    """Return the default AIQuestionService instance."""

    return _default_service


def generate_question(*args, **kwargs):
    """Proxy to the default service for backwards compatibility."""

    return _default_service.generate_question(*args, **kwargs)


def evaluate_answer(*args, **kwargs):
    """Proxy to the default service for backwards compatibility."""

    return _default_service.evaluate_answer(*args, **kwargs)


__all__ = [
    "AIQuestionService",
    "OpenAIProvider",
    "QUESTION_PROMPTS",
    "EVAL_PROMPT",
    "get_service",
    "generate_question",
    "evaluate_answer",
]
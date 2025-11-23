"""High-level AI helpers for question generation and evaluation."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from utils.config import settings

from .prompts import QUESTION_PROMPTS, EVAL_PROMPT
from .provider import OpenAIProvider

logger = logging.getLogger(__name__)


class AIQuestionService:
    """Thin wrapper over OpenAI chat completions for quiz workflows."""

    def __init__(
        self,
        provider: Optional[OpenAIProvider] = None,
        question_prompts: Optional[Dict[int, str]] = None,
        eval_prompt: Optional[str] = None,
    ) -> None:
        self._provider = provider or OpenAIProvider()
        self._question_prompts = question_prompts or QUESTION_PROMPTS
        self._eval_prompt = eval_prompt or EVAL_PROMPT

    def _build_question_prompt(
        self,
        difficulty: int,
        category: str,
        subcategory: str,
        keyword: str,
        style_modifier: Optional[str],
    ) -> str:
        prompt_template = self._question_prompts[difficulty]
        difficulty_label = {1: "easy", 2: "intermediate", 3: "advanced"}[difficulty]
        return prompt_template.format(
            category=category,
            subcategory=subcategory,
            keyword=keyword,
            difficulty_label=difficulty_label,
            style_modifier=style_modifier or "general explanation",
        )

    def generate_question(
        self,
        category: str,
        subcategory: str,
        keyword: str,
        difficulty: int,
        style_modifier: Optional[str] = None,
    ):
        logger.info(
            "openai_generate_question_start category=%s subcategory=%s keyword=%s difficulty=%d style_modifier=%s model=%s",
            category,
            subcategory,
            keyword,
            difficulty,
            style_modifier,
            settings.openai_model,
        )

        prompt = self._build_question_prompt(
            difficulty, category, subcategory, keyword, style_modifier
        )

        client = self._provider.get_client()
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.openai_temperature_question,
            max_tokens=settings.openai_max_tokens_question,
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("OpenAI returned empty response")

        tokens_used = 0
        if hasattr(response, "usage") and response.usage is not None:
            tokens_used = response.usage.total_tokens

        logger.info(
            "openai_generate_question_success category=%s subcategory=%s keyword=%s difficulty=%d tokens_used=%d",
            category,
            subcategory,
            keyword,
            difficulty,
            tokens_used,
        )
        return result.strip()

    def evaluate_answer(
        self,
        question: str,
        answer: str,
        difficulty: int,
        keyword: Optional[str] = None,
    ):
        logger.info(
            "openai_evaluate_answer_start difficulty=%d answer_length=%d keyword=%s model=%s",
            difficulty,
            len(answer),
            keyword,
            settings.openai_model,
        )

        difficulty_label = {1: "basic", 2: "intermediate", 3: "advanced"}[difficulty]
        prompt = self._eval_prompt.format(
            question=question,
            answer=answer,
            difficulty_label=difficulty_label,
            keyword=keyword or "N/A",
        )

        client = self._provider.get_client()
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.openai_temperature_eval,
            max_tokens=settings.openai_max_tokens_eval,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned empty response")

        tokens_used = 0
        if hasattr(response, "usage") and response.usage is not None:
            tokens_used = response.usage.total_tokens

        # Strip markdown code blocks if present (```json ... ```)
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]  # Remove ```json
        elif cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]  # Remove ```
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]  # Remove trailing ```
        cleaned_content = cleaned_content.strip()
        
        try:
            evaluation = json.loads(cleaned_content)
            
            # Validate the response has required fields
            if not isinstance(evaluation, dict):
                raise ValueError("AI response is not a JSON object")
            if "score" not in evaluation or "feedback" not in evaluation:
                raise ValueError("AI response missing required fields (score/feedback)")
            
            logger.info(
                "openai_evaluate_answer_success difficulty=%d tokens_used=%d score=%s",
                difficulty,
                tokens_used,
                evaluation.get("score", "N/A"),
            )
            return {
                "score": evaluation.get("score", "N/A"),
                "feedback": evaluation.get("feedback", "No feedback provided"),
            }
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "ai_response_invalid difficulty=%d error=%s content=%s",
                difficulty,
                str(exc),
                content[:200],  # Log first 200 chars for debugging
            )
            # Raise the error so it can be handled at the route level
            raise ValueError(f"AI evaluation failed: Invalid response format - {str(exc)}") from exc
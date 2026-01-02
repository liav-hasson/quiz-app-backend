"""High-level AI helpers for question generation and evaluation."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from common.utils.config import settings

from .prompts import QUESTION_PROMPTS, EVAL_PROMPT, MULTIPLAYER_QUESTION_PROMPTS, PERFECT_ANSWER_PROMPT
from .provider import OpenAIProvider

logger = logging.getLogger(__name__)


class AIQuestionService:
    """Thin wrapper over OpenAI chat completions for quiz workflows."""

    def __init__(
        self,
        provider: Optional[OpenAIProvider] = None,
        question_prompts: Optional[Dict[int, str]] = None,
        eval_prompt: Optional[str] = None,
        multiplayer_prompts: Optional[Dict[int, str]] = None,
        perfect_answer_prompt: Optional[str] = None,
    ) -> None:
        self._provider = provider or OpenAIProvider()
        self._question_prompts = question_prompts or QUESTION_PROMPTS
        self._eval_prompt = eval_prompt or EVAL_PROMPT
        self._multiplayer_prompts = multiplayer_prompts or MULTIPLAYER_QUESTION_PROMPTS
        self._perfect_answer_prompt = perfect_answer_prompt or PERFECT_ANSWER_PROMPT

    def _get_provider(self, custom_api_key: Optional[str] = None) -> OpenAIProvider:
        """Get a provider, optionally with a custom API key."""
        if custom_api_key:
            return OpenAIProvider(api_key=custom_api_key)
        return self._provider

    def _get_model(self, custom_model: Optional[str] = None) -> str:
        """Get the model to use, with optional override."""
        return custom_model if custom_model else settings.openai_model

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
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
    ):
        model = self._get_model(custom_model)
        logger.info(
            "openai_generate_question_start category=%s subcategory=%s keyword=%s difficulty=%d style_modifier=%s model=%s custom_key=%s",
            category,
            subcategory,
            keyword,
            difficulty,
            style_modifier,
            model,
            "yes" if custom_api_key else "no",
        )

        prompt = self._build_question_prompt(
            difficulty, category, subcategory, keyword, style_modifier
        )

        provider = self._get_provider(custom_api_key)
        response = provider.chat_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.openai_max_tokens_question,
            temperature=settings.openai_temperature_question,
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

    def generate_multiplayer_question(
        self,
        category: str,
        subcategory: str,
        keyword: str,
        difficulty: int,
        style_modifier: Optional[str] = None,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
    ) -> Dict[str, any]:
        """Generate a multiple-choice question for multiplayer mode with structured JSON response.
        
        Returns:
            Dict with keys: question, options (list of 4), correct_answer, explanation
        """
        model = self._get_model(custom_model)
        logger.info(
            "openai_generate_multiplayer_question_start category=%s subcategory=%s keyword=%s difficulty=%d style_modifier=%s model=%s custom_key=%s",
            category,
            subcategory,
            keyword,
            difficulty,
            style_modifier,
            model,
            "yes" if custom_api_key else "no",
        )

        prompt_template = self._multiplayer_prompts[difficulty]
        difficulty_label = {1: "easy", 2: "intermediate", 3: "advanced"}[difficulty]
        prompt = prompt_template.format(
            category=category,
            subcategory=subcategory,
            keyword=keyword,
            difficulty_label=difficulty_label,
            style_modifier=style_modifier or "general knowledge",
        )

        provider = self._get_provider(custom_api_key)
        response = provider.chat_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.openai_max_tokens_question + 100,  # Slightly more tokens for structured output
            temperature=settings.openai_temperature_question,
            response_format={"type": "json_object"},  # Enforce JSON response
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned empty response")

        tokens_used = 0
        if hasattr(response, "usage") and response.usage is not None:
            tokens_used = response.usage.total_tokens

        # Parse and validate JSON response
        try:
            question_data = json.loads(content.strip())
            
            # Validate required fields
            required_fields = ["question", "options", "correct_answer"]
            for field in required_fields:
                if field not in question_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate options structure
            if not isinstance(question_data["options"], list) or len(question_data["options"]) != 4:
                raise ValueError("Options must be a list of exactly 4 items")
            
            # Validate correct_answer is a single letter (A, B, C, or D)
            valid_letters = ["A", "B", "C", "D"]
            if question_data["correct_answer"] not in valid_letters:
                raise ValueError(f"correct_answer must be one of {valid_letters}, got: {question_data['correct_answer']}")
            
            # Shuffle options randomly to avoid bias (AI tends to put correct answer first)
            import random
            options = question_data["options"]
            correct_answer_letter = question_data["correct_answer"]
            
            # Find the index of the correct answer (0-3)
            correct_index = ord(correct_answer_letter) - ord('A')
            
            # Create a list of indices and shuffle them
            indices = [0, 1, 2, 3]
            random.shuffle(indices)
            
            # Reorder options according to shuffled indices
            shuffled_options = [options[i] for i in indices]
            
            # Find where the correct answer moved to
            new_correct_index = indices.index(correct_index)
            new_correct_letter = chr(ord('A') + new_correct_index)
            
            # Update question data with shuffled options and new correct answer position
            question_data["options"] = shuffled_options
            question_data["correct_answer"] = new_correct_letter
            
            # Add empty explanation if not provided (optional field)
            if "explanation" not in question_data:
                question_data["explanation"] = ""
            
            logger.info(
                "openai_generate_multiplayer_question_success category=%s subcategory=%s keyword=%s difficulty=%d tokens_used=%d shuffled=%s->%s",
                category,
                subcategory,
                keyword,
                difficulty,
                tokens_used,
                correct_answer_letter,
                new_correct_letter,
            )
            
            return question_data
            
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(
                "ai_multiplayer_question_invalid difficulty=%d error=%s content=%s",
                difficulty,
                str(exc),
                content[:200],
            )
            raise ValueError(f"AI question generation failed: {str(exc)}") from exc

    def evaluate_answer(
        self,
        question: str,
        answer: str,
        difficulty: int,
        keyword: Optional[str] = None,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
    ):
        model = self._get_model(custom_model)
        logger.info(
            "openai_evaluate_answer_start difficulty=%d answer_length=%d keyword=%s model=%s custom_key=%s",
            difficulty,
            len(answer),
            keyword,
            model,
            "yes" if custom_api_key else "no",
        )

        difficulty_label = {1: "basic", 2: "intermediate", 3: "advanced"}[difficulty]
        prompt = self._eval_prompt.format(
            question=question,
            answer=answer,
            difficulty_label=difficulty_label,
            keyword=keyword or "N/A",
        )

        provider = self._get_provider(custom_api_key)
        response = provider.chat_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.openai_max_tokens_eval,
            temperature=settings.openai_temperature_eval,
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

    def generate_perfect_answer(
        self,
        question: str,
        custom_api_key: Optional[str] = None,
        custom_model: Optional[str] = None,
    ):
        """Generate a perfect 10/10 answer for a given question.
        
        Args:
            question: The question to generate a perfect answer for
            custom_api_key: Optional custom OpenAI API key
            custom_model: Optional custom model name
            
        Returns:
            Dict with key 'perfect_answer' containing the generated answer text
        """
        model = self._get_model(custom_model)
        logger.info(
            "openai_generate_perfect_answer_start question_length=%d model=%s custom_key=%s",
            len(question),
            model,
            "yes" if custom_api_key else "no",
        )

        prompt = self._perfect_answer_prompt.format(question=question)

        provider = self._get_provider(custom_api_key)
        response = provider.chat_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.openai_max_tokens_eval,  # Similar length to evaluation feedback
            temperature=0.7,  # Slightly creative but mostly consistent
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned empty response")

        tokens_used = 0
        if hasattr(response, "usage") and response.usage is not None:
            tokens_used = response.usage.total_tokens

        logger.info(
            "openai_generate_perfect_answer_success tokens_used=%d answer_length=%d",
            tokens_used,
            len(content),
        )
        
        return {
            "perfect_answer": content.strip()
        }
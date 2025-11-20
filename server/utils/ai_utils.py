"""
AI utilities for generating quiz questions and evaluating answers using OpenAI.
"""

import logging
import json
import boto3
from openai import OpenAI

# Importing config class in config.py
from utils.config import Config

logger = logging.getLogger(__name__)


def _get_api_key_from_ssm():
    """
    Try to read the API key from AWS SSM Parameter Store.
    """
    logger.info("fetching_api_key_from_ssm parameter=%s", Config.SSM_PARAMETER_NAME)
    try:
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=Config.SSM_PARAMETER_NAME, WithDecryption=True)
        logger.info("api_key_fetched_from_ssm")
        return resp["Parameter"]["Value"]
    except Exception as e:
        logger.error("ssm_api_key_fetch_failed error=%s", str(e))
        raise


def _get_openai_client():
    """Construct and return an OpenAI client.

    This defers import/runtime errors until the functionality is used and
    allows static analysis in environments without third-party packages.
    """
    api_key = Config.OPENAI_API_KEY
    if not api_key:
        logger.debug("api_key_not_in_config_fetching_from_ssm")
        api_key = _get_api_key_from_ssm()
    else:
        logger.debug("using_api_key_from_config")

    return OpenAI(api_key=api_key)


def generate_question(category, subcategory, keyword, difficulty, style_modifier=None):
    """Generate a question for a keyword and difficulty level.

    Args:
        category: Main topic category (e.g., "Kubernetes", "Docker")
        subcategory: Subcategory within topic (e.g., "Commands", "Architecture")
        keyword: Specific keyword to focus on
        difficulty: Difficulty level (1=basic, 2=intermediate, 3=advanced)
        style_modifier: Optional style modifier to guide question format
    """
    logger.info(
        "openai_generate_question_start category=%s subcategory=%s keyword=%s difficulty=%d style_modifier=%s model=%s",
        category,
        subcategory,
        keyword,
        difficulty,
        style_modifier,
        Config.OPENAI_MODEL,
    )

    difficulty_label = {1: "easy", 2: "intermediate", 3: "advanced"}[difficulty]

    # Build the prompt
    prompt = Config.QUESTION_PROMPT[difficulty].format(
        category=category,
        subcategory=subcategory,
        keyword=keyword,
        difficulty_label=difficulty_label,
        style_modifier=style_modifier if style_modifier else "general explanation",
    )

    try:
        client = _get_openai_client()
        api_response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=Config.OPENAI_TEMPERATURE_QUESTION,
            max_tokens=Config.OPENAI_MAX_TOKENS_QUESTION,
        )
        result = api_response.choices[0].message.content
        if result is None:
            raise ValueError("OpenAI returned empty response")
        result = result.strip()

        tokens_used = 0
        if hasattr(api_response, "usage") and api_response.usage is not None:
            tokens_used = api_response.usage.total_tokens

        logger.info(
            "openai_generate_question_success category=%s subcategory=%s keyword=%s difficulty=%d tokens_used=%d",
            category,
            subcategory,
            keyword,
            difficulty,
            tokens_used,
        )
        return result
    except Exception as e:
        logger.error(
            "openai_generate_question_failed category=%s subcategory=%s keyword=%s error=%s",
            category,
            subcategory,
            keyword,
            str(e),
            exc_info=True,
        )
        raise


def evaluate_answer(question, answer, difficulty, keyword=None):
    """Generate a response based on the question and answer.

    Args:
        question: The question that was asked
        answer: User's answer to evaluate
        difficulty: Difficulty level (1-3)
        keyword: Optional keyword for additional context
    """
    logger.info(
        "openai_evaluate_answer_start difficulty=%d answer_length=%d keyword=%s model=%s",
        difficulty,
        len(answer),
        keyword,
        Config.OPENAI_MODEL,
    )

    difficulty_label = {1: "basic", 2: "intermediate", 3: "advanced"}[difficulty]

    prompt = Config.EVAL_PROMPT.format(
        question=question,
        answer=answer,
        difficulty_label=difficulty_label,
        keyword=keyword if keyword else "N/A",
    )

    try:
        client = _get_openai_client()
        api_response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=Config.OPENAI_TEMPERATURE_EVAL,
            max_tokens=Config.OPENAI_MAX_TOKENS_EVAL,
        )
        result = api_response.choices[0].message.content
        if result is None:
            raise ValueError("OpenAI returned empty response")
        result = result.strip()

        tokens_used = 0
        if hasattr(api_response, "usage") and api_response.usage is not None:
            tokens_used = api_response.usage.total_tokens

        # Parse JSON response from AI
        try:
            evaluation = json.loads(result)
            score = evaluation.get("score", "N/A")
            feedback_text = evaluation.get("feedback", "No feedback provided")
            
            logger.info(
                "openai_evaluate_answer_success difficulty=%d tokens_used=%d score=%s",
                difficulty,
                tokens_used,
                score,
            )
            
            # Return structured dict with score and feedback
            return {
                "score": score,
                "feedback": feedback_text
            }
        except json.JSONDecodeError as json_err:
            # Fallback: AI didn't return valid JSON, treat as plain feedback
            logger.warning(
                "ai_response_not_json difficulty=%d error=%s, treating as plain text",
                difficulty,
                str(json_err)
            )
            return {
                "score": "N/A",
                "feedback": result
            }
        
    except Exception as e:
        logger.error(
            "openai_evaluate_answer_failed difficulty=%d error=%s",
            difficulty,
            str(e),
            exc_info=True,
        )
        raise

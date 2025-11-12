"""
AI utilities for generating quiz questions and evaluating answers using OpenAI.
"""
import logging
import boto3 
from openai import OpenAI 

# Importing config class in config.py
from config import Config

logger = logging.getLogger(__name__)

def _get_api_key_from_ssm():
    """
    Try to read the API key from AWS SSM Parameter Store.
    """
    logger.info("fetching_api_key_from_ssm parameter=%s", Config.SSM_PARAMETER_NAME)
    try:
        ssm = boto3.client('ssm')
        resp = ssm.get_parameter(Name=Config.SSM_PARAMETER_NAME, WithDecryption=True)
        logger.info("api_key_fetched_from_ssm")
        return resp['Parameter']['Value']
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

def generate_question(category, keyword, difficulty):
    """Generate a question for a keyword and difficulty level."""
    logger.info(
        "openai_generate_question_start category=%s keyword=%s difficulty=%d model=%s",
        category,
        keyword,
        difficulty,
        Config.OPENAI_MODEL
    )

    difficulty_label = {
        1: "basic level",
        2: "intermediate level",
        3: "advanced level"
    }[difficulty]

    prompt = QUESTION_PROMPT[difficulty].format(
        keyword=keyword,
        category=category,
        difficulty_label=difficulty_label
    )

    try:
        client = _get_openai_client()
        api_response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        result = api_response.choices[0].message.content.strip()
        logger.info(
            "openai_generate_question_success category=%s keyword=%s difficulty=%d tokens_used=%d",
            category,
            keyword,
            difficulty,
            api_response.usage.total_tokens if hasattr(api_response, 'usage') else 0
        )
        return result
    except Exception as e:
        logger.error(
            "openai_generate_question_failed category=%s keyword=%s error=%s",
            category,
            keyword,
            str(e),
            exc_info=True
        )
        raise

def evaluate_answer(question, answer, difficulty):
    """Generate a response based on the question and answer."""
    logger.info(
        "openai_evaluate_answer_start difficulty=%d answer_length=%d model=%s",
        difficulty,
        len(answer),
        Config.OPENAI_MODEL
    )

    difficulty_label = {
        1: "basic level",
        2: "intermediate level",
        3: "advanced level"
    }[difficulty]

    prompt = EVAL_PROMPT.format(
        question=question,
        answer=answer,
        difficulty_label=difficulty_label
    )

    try:
        client = _get_openai_client()
        api_response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        result = api_response.choices[0].message.content.strip()
        logger.info(
            "openai_evaluate_answer_success difficulty=%d tokens_used=%d",
            difficulty,
            api_response.usage.total_tokens if hasattr(api_response, 'usage') else 0
        )
        return result
    except Exception as e:
        logger.error(
            "openai_evaluate_answer_failed difficulty=%d error=%s",
            difficulty,
            str(e),
            exc_info=True
        )
        raise


QUESTION_PROMPT = {
    1: (
        "You are a DevOps interviewer. Create a short basic question on "
        '"{category}" in relation to "{keyword}".\n'
        "- 1 sentence (≤25 words), answer ≤3 sentences.\n"
        "- Ask only 1 question. No answer."
    ),

    2: (
        "You are a DevOps interviewer. Create a short intermediate question "
        'on "{category}" in relation to "{keyword}".\n'
        "- 1 sentence (≤25 words), answer ≤3 sentences.\n"
        "- Ask only 1 question. No answer."
    ),

    3: (
        "You are a DevOps interviewer. Create a short advanced and creative "
        'question on "{category}" in relation to "{keyword}".\n'
        "- 1 sentence (≤25 words), answer ≤3 sentences.\n"
        "- Ask only 1 question. No answer."
    )
}

EVAL_PROMPT = (
    "You are a DevOps teacher.\n"
    "I will give you an interview question and the user's answer.\n"
    "The candidate's answer should be brief (≤3 sentences).\n\n"
    "The question difficulty: {difficulty_label}\n"
    'Q: "{question}"\n'
    'A: "{answer}"\n\n'
    "Tasks:\n"
    "1. Score 1-10 (10 = excellent).\n"
    "2. Feedback:\n"
    "   - 9-10: brief praise.\n"
    "   - 6-8: what is missing.\n"
    "   - ≤5: main gap + what to study.\n"
    "3. Ignore grammar - focus on the core purpose of the answer.\n"
    "4. Review based on the question difficulty.\n\n"
    "Format:\n"
    "Your score: <number>/10\n"
    "feedback: <text>\n"
)

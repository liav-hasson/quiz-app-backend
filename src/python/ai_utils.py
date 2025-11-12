"""
AI utilities for generating quiz questions and evaluating answers using OpenAI.
"""
import boto3 
from openai import OpenAI 

# Importing config class in config.py
from config import Config

def _get_api_key_from_ssm():
    """
    Try to read the API key from AWS SSM Parameter Store.
    """

    ssm = boto3.client('ssm')
    resp = ssm.get_parameter(Name=Config.SSM_PARAMETER_NAME, WithDecryption=True)
    return resp['Parameter']['Value']


def _get_openai_client():
    """Construct and return an OpenAI client.

    This defers import/runtime errors until the functionality is used and
    allows static analysis in environments without third-party packages.
    """

    api_key = Config.OPENAI_API_KEY
    if not api_key:
        api_key = _get_api_key_from_ssm()

    return OpenAI(api_key=api_key)

def generate_question(category, keyword, difficulty):
    """Generate a question for a keyword and difficulty level."""

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

    client = _get_openai_client()
    api_response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return api_response.choices[0].message.content.strip()

def evaluate_answer(question, answer, difficulty):
    """Generate a response based on the question and answer."""

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

    client = _get_openai_client()
    api_response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return api_response.choices[0].message.content.strip()


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

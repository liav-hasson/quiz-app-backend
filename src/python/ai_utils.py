"""
AI utility functions for generating quiz questions and evaluating answers.
Uses OpenAI API for question generation and answer evaluation.
"""
import os

# Optional third-party imports. Wrap in try/except so linters and static
# checks in environments that don't have these packages installed won't
# immediately fail on import. At runtime, missing packages will raise a
# clear RuntimeError when trying to use functionality that requires them.
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive for linting environments
    boto3 = None  # type: ignore
    BOTO3_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - defensive for linting environments
    OpenAI = None  # type: ignore
def _get_api_key_from_ssm(parameter_name='/devops-quiz/openai-api-key'):
    """Try to read the API key from AWS SSM Parameter Store.

    Returns the key string or raises RuntimeError if boto3 isn't available
    or the parameter can't be read.
    """
    if not BOTO3_AVAILABLE or boto3 is None:
        raise RuntimeError('boto3 is required to read API key from SSM')

    ssm = boto3.client('ssm')
    resp = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    return resp['Parameter']['Value']


def _get_openai_client():
    """Lazily construct and return an OpenAI client.

    This defers import/runtime errors until the functionality is used and
    allows static analysis in environments without third-party packages.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        api_key = _get_api_key_from_ssm()

    if not OPENAI_AVAILABLE or OpenAI is None:
        raise RuntimeError('openai package is required to use AI utilities')

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
        model="gpt-4o-mini",
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
        model="gpt-4o-mini",
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

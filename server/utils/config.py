"""
Flask application configuration module.
"""
import os

class Config:  # pylint: disable=too-few-public-methods
    """Flask application configuration."""

    # Flask settings
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    # the following comment excludes the line from bandit security testing
    # avoids failing due to "hardcoded_bind_all_interfaces"
    HOST = os.environ.get("FLASK_HOST", "0.0.0.0")  # nosec B104 - intentional for containerized app
    PORT = int(os.environ.get("FLASK_PORT", 5000))

    # OpenAI settings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE_QUESTION = float(os.environ.get("OPENAI_TEMPERATURE_QUESTION", "0.7"))
    OPENAI_TEMPERATURE_EVAL = float(os.environ.get("OPENAI_TEMPERATURE_EVAL", "0.5"))
    OPENAI_MAX_TOKENS_QUESTION = int(os.environ.get("OPENAI_MAX_TOKENS_QUESTION", "200"))
    OPENAI_MAX_TOKENS_EVAL = int(os.environ.get("OPENAI_MAX_TOKENS_EVAL", "300"))

    # AWS SSM settings (for API key retrieval)
    SSM_PARAMETER_NAME = os.environ.get(
        "SSM_PARAMETER_NAME",
        "/devops-quiz/openai-api-key"
    )

    # Question generation prompts
    QUESTION_PROMPT = {
        1: (
            "You are a DevOps interviewer, create a {difficulty_label} technical question.\n\n"
            "Topic: {subcategory} in {category}.\n"
            "Focus keyword: {keyword}\n"
            "Question style: {style_modifier}\n\n"
            "Create a SHORT, CLEAR question that:\n"
            "- Is appropriate for entry-level DevOps engineers.\n"
            "- Can be answered in 2-3 sentences.\n\n"
            "Generate only the question, no additional text."
        ),
        2: (
            "You are a DevOps interviewer, create an {difficulty_label} technical question.\n\n"
            "Topic: {subcategory} in {category}\n"
            "Focus keyword: {keyword}\n"
            "Question style: {style_modifier}\n\n"
            "Create a SHORT, PRACTICAL question that:\n"
            "- Is appropriate for mid-level DevOps engineers.\n"
            "- Can be answered in 3-4 sentences.\n\n"
            "Generate only the question, no additional text."
        ),
        3: (
            "You are a DevOps interviewer, create an {difficulty_label} level technical question.\n\n"
            "Topic: {subcategory} in {category}\n"
            "Focus keyword: {keyword}\n"
            "Question style: {style_modifier}\n\n"
            "Create a SHORT, CHALLENGING question that:\n"
            "- Is appropriate for senior DevOps engineers.\n"
            "- Can be answered in 4-5 sentences.\n\n"
            "Generate only the question, no additional text."
        )
    }

    # Answer evaluation prompt
    EVAL_PROMPT = (
        "You are a DevOps teacher.\n"
        "I will give you a question and the student's answer for review.\n"
        "The question difficulty: {difficulty_label}.\n"
        "Review based on the question difficulty.\n"
        'Q: "{question}"\n'
        'A: "{answer}"\n\n'
        "Tasks:\n"
        "1. Score 1-10 (10 = excellent).\n"
        "2. Give short, constructive feedback on the user's answer quality, and"
        "briefly correct and explain any mistakes and suggest topics to study.\n"
        "3. Expect a short, 3-5 sentences answer from the student.\n"
        "4. Ignore casing and punctuation in evaluation.\n"
        "Format:\n"
        "Your score: <number>/10\n"
        "feedback: <text>\n"
    )
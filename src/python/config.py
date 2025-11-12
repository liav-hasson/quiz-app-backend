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

    # AWS SSM settings (for API key retrieval)
    SSM_PARAMETER_NAME = os.environ.get(
        "SSM_PARAMETER_NAME",
        "/devops-quiz/openai-api-key"
    )
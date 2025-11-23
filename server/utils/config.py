"""Runtime configuration helpers for the Quiz backend."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Optional

import boto3


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration loaded from the environment."""

    debug: bool
    host: str
    port: int
    jwt_exp_days: int
    jwt_ssm_parameter_name: str
    google_client_id_parameter: str
    openai_api_key: Optional[str]
    openai_model: str
    openai_temperature_question: float
    openai_temperature_eval: float
    openai_max_tokens_question: int
    openai_max_tokens_eval: int
    openai_ssm_parameter_name: str
    require_authentication: bool

    @staticmethod
    def from_env(env: Mapping[str, str] | None = None) -> "Settings":
        env = env or os.environ
        return Settings(

            # toggle Flask debugger (disabled in prod)
            debug=env.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes"),
            # the following comment disables bandit error (binding to all interfaces)
            host=env.get("FLASK_HOST", "0.0.0.0"),  # nosec B104 - Required for containerized deployment
            port=int(env.get("FLASK_PORT", "5000")),

            # auth parameters 
            jwt_exp_days=int(env.get("JWT_EXP_DAYS", "7")),
            jwt_ssm_parameter_name=env.get("JWT_SSM_PARAMETER", "/quiz-app/jwt-secret"),
            google_client_id_parameter=env.get(
                "GOOGLE_CLIENT_ID_PARAMETER", "/quiz-app/google-client-id"
            ),
            # variable to disable JWT auth in development
            require_authentication=env.get("REQUIRE_AUTHENTICATION", "true").lower()
            in ("1", "true", "yes"),

            # ai agent variables
            openai_api_key=env.get("OPENAI_API_KEY"),
            openai_model=env.get("OPENAI_MODEL", "gpt-4o-mini"),
            openai_temperature_question=float(
                env.get("OPENAI_TEMPERATURE_QUESTION", "0.7")
            ),
            openai_temperature_eval=float(env.get("OPENAI_TEMPERATURE_EVAL", "0.5")),
            openai_max_tokens_question=int(env.get("OPENAI_MAX_TOKENS_QUESTION", "200")),
            openai_max_tokens_eval=int(env.get("OPENAI_MAX_TOKENS_EVAL", "300")),
            openai_ssm_parameter_name=env.get(
                "OPENAI_SSM_PARAMETER", "/devops-quiz/openai-api-key"
            ),            
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings loaded from environment variables."""

    return Settings.from_env()


settings = get_settings()


def get_jwt_secret(ssm_client=None) -> str:
    """Fetch JWT secret from environment variable or AWS SSM Parameter Store.
    
    Priority:
    1. JWT_SECRET env var (docker-compose)
    2. SSM Parameter Store (EKS with IRSA)
    """
    logger = logging.getLogger(__name__)

    jwt_secret = os.environ.get("JWT_SECRET")
    if jwt_secret:
        logger.debug("using_jwt_secret_from_environment")
        return jwt_secret

    logger.info(
        "fetching_jwt_secret_from_ssm parameter=%s", settings.jwt_ssm_parameter_name
    )
    try:
        client = ssm_client or boto3.client("ssm")
        resp = client.get_parameter(
            Name=settings.jwt_ssm_parameter_name, WithDecryption=True
        )
        logger.info("jwt_secret_fetched_from_ssm")
        return resp["Parameter"]["Value"]
    except Exception as exc:  # pragma: no cover - relies on AWS infra
        logger.error("jwt_secret_fetch_failed error=%s", str(exc))
        raise ValueError(f"Failed to retrieve JWT secret: {str(exc)}") from exc


def get_google_client_id(ssm_client=None) -> str:
    """Fetch Google Client ID from environment variable or AWS SSM Parameter Store.
    
    Priority:
    1. GOOGLE_CLIENT_ID env var (docker-compose)
    2. SSM Parameter Store (EKS with IRSA)
    """
    logger = logging.getLogger(__name__)

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if google_client_id:
        logger.debug("using_google_client_id_from_environment")
        return google_client_id

    logger.info(
        "fetching_google_client_id_from_ssm parameter=%s",
        settings.google_client_id_parameter,
    )
    try:
        client = ssm_client or boto3.client("ssm")
        resp = client.get_parameter(
            Name=settings.google_client_id_parameter, WithDecryption=True
        )
        logger.info("google_client_id_fetched_from_ssm")
        return resp["Parameter"]["Value"]
    except Exception as exc:  # pragma: no cover
        logger.error("google_client_id_fetch_failed error=%s", str(exc))
        raise ValueError(f"Failed to retrieve Google Client ID: {str(exc)}") from exc


# Backwards compatibility alias for legacy imports
Config = settings
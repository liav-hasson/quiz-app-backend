"""OpenAI client provider with AWS SSM fallback."""

from __future__ import annotations

import logging
import os
from typing import Optional

import boto3
from openai import OpenAI

from utils.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """Resolve API credentials and hand out OpenAI client instances.
    
    Priority for API key resolution:
    1. Explicit api_key parameter (testing)
    2. OPENAI_API_KEY env var (docker-compose)
    3. SSM Parameter Store (EKS with IRSA)
    """

    def __init__(self, api_key: Optional[str] = None, ssm_client=None) -> None:
        self._explicit_api_key = api_key
        self._ssm_client = ssm_client

    def _fetch_api_key_from_ssm(self) -> str:
        logger.info(
            "fetching_openai_api_key_from_ssm parameter=%s",
            settings.openai_ssm_parameter_name,
        )
        client = self._ssm_client or boto3.client(
            "ssm", region_name=os.environ.get("AWS_REGION", "eu-north-1")
        )
        response = client.get_parameter(
            Name=settings.openai_ssm_parameter_name, WithDecryption=True
        )
        logger.info("openai_api_key_fetched_from_ssm")
        return response["Parameter"]["Value"]

    def _resolve_api_key(self) -> str:
        if self._explicit_api_key:
            logger.debug("using_explicit_openai_api_key")
            return self._explicit_api_key

        if settings.openai_api_key:
            logger.debug("using_openai_api_key_from_env")
            return settings.openai_api_key

        logger.debug("openai_api_key_missing_fetching_from_ssm")
        return self._fetch_api_key_from_ssm()

    def get_client(self) -> OpenAI:
        """Return an authenticated OpenAI client."""

        api_key = self._resolve_api_key()
        return OpenAI(api_key=api_key)
"""OpenAI client provider with AWS SSM fallback."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from openai import OpenAI

from common.utils.config import settings

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

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: Optional[float] = None,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Make a chat completion request with automatic parameter adaptation.
        
        Tries with max_tokens first. If the model doesn't support it (newer reasoning
        models like o1, o3), automatically retries with max_completion_tokens.
        
        Args:
            model: The model name (e.g., 'gpt-4o-mini', 'o1', 'o3-mini')
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens for the response
            temperature: Optional temperature (omitted on retry for reasoning models)
            response_format: Optional response format (e.g., {"type": "json_object"})
        
        Returns:
            The OpenAI chat completion response object
        """
        client = self.get_client()
        
        # Build base params
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            params["temperature"] = temperature
        if response_format is not None:
            params["response_format"] = response_format
        
        try:
            return client.chat.completions.create(**params)
        except Exception as first_error:
            error_str = str(first_error).lower()
            # Check if the error is about unsupported max_tokens parameter
            if "max_tokens" in error_str and "unsupported" in error_str:
                logger.info(
                    "chat_completion_retry model=%s reason=max_tokens_unsupported",
                    model,
                )
                # Retry with max_completion_tokens instead
                # Remove max_tokens and temperature (reasoning models don't support custom temperature)
                retry_params: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "max_completion_tokens": max_tokens,
                }
                if response_format is not None:
                    retry_params["response_format"] = response_format
                
                return client.chat.completions.create(**retry_params)
            else:
                # Not a parameter error, re-raise
                raise
"""Google ID token verification helpers."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

try:  # pragma: no cover - optional dependency
    from google.auth.transport import requests
    from google.oauth2 import id_token
except ImportError:  # pragma: no cover - fallback for local dev/tests
    requests = None  # type: ignore
    id_token = None  # type: ignore

from common.utils.config import get_google_client_id

logger = logging.getLogger(__name__)


class GoogleVerificationError(Exception):
    """Base error for Google token verification issues."""

    status_code = 500


class GoogleClientNotConfiguredError(GoogleVerificationError):
    status_code = 500


class InvalidGoogleTokenError(GoogleVerificationError):
    status_code = 401


class GoogleTokenVerifier:
    """Wraps google.oauth2 token verification for easier testing."""

    def __init__(
        self,
        client_id_provider: Optional[Callable[[], str]] = None,
        request_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._client_id_provider = client_id_provider or get_google_client_id
        self._request_factory = request_factory or (requests.Request if requests else None)

    def verify(self, google_id_token: str) -> Dict[str, Any]:
        if not id_token or not self._request_factory:
            raise GoogleVerificationError(
                "Google verification libraries are not installed"
            )

        client_id = self._client_id_provider()
        if not client_id:
            logger.error("google_client_id_not_configured")
            raise GoogleClientNotConfiguredError("OAuth not properly configured")

        try:
            request = self._request_factory()
            return id_token.verify_oauth2_token(google_id_token, request, client_id)
        except ValueError as exc:
            logger.warning("invalid_google_token error=%s", str(exc))
            raise InvalidGoogleTokenError("Invalid Google token") from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("google_token_verification_failed error=%s", str(exc))
            raise GoogleVerificationError("Failed to verify Google token") from exc
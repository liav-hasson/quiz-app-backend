"""JWT token helper utilities."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

import jwt
from jwt import InvalidTokenError
import pytz

from common.utils.config import get_jwt_secret, settings


class TokenService:
    """Issuing application JWTs with pluggable secret providers."""

    def __init__(
        self,
        secret_provider: Optional[Callable[[], str]] = None,
        expires_days: Optional[int] = None,
        timezone: str = "Asia/Jerusalem",
        algorithm: str = "HS256",
    ) -> None:
        self._secret_provider = secret_provider or get_jwt_secret
        self._expires_days = expires_days or settings.jwt_exp_days
        self._timezone = pytz.timezone(timezone)
        self._algorithm = algorithm

    def generate(self, user: Dict[str, Any]) -> str:
        """Return a signed JWT for the provided user payload.
        
        This function creates the "Session Token" that the frontend will use
        to prove who the user is for all future requests.
        
        It includes:
        - sub: The user's unique ID (Subject)
        - email: The user's email
        - exp: When this token expires (so they have to login again eventually)
        - iat: When this token was created (Issued At)
        """

        secret = self._secret_provider()
        now = datetime.now(self._timezone)
        payload = {
            "sub": user.get("_id"),
            "email": user.get("email"),
            "name": user.get("name"),
            "exp": now + timedelta(days=self._expires_days),
            "iat": now,
        }
        # We sign the token with our secret key so no one can fake it
        return jwt.encode(payload, secret, algorithm=self._algorithm)

    def decode(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT.
        
        This checks if the token sent by the user is valid.
        If the signature doesn't match (wrong secret) or the token is expired,
        this will raise an error.
        """

        secret = self._secret_provider()
        return jwt.decode(token, secret, algorithms=[self._algorithm])
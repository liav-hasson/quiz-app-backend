"""Rate limiting utilities using Redis.

Provides sliding window rate limiting for API endpoints.
Configuration is centralized in common/utils/config.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from common.redis_client import get_redis_client
from common.utils.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    max_requests: int  # Maximum requests allowed
    window_seconds: int  # Time window in seconds
    key_prefix: str = "ratelimit"  # Redis key prefix
    
    @property
    def key_template(self) -> str:
        """Template for Redis key: {prefix}:{resource}:{user_id}"""
        return f"{self.key_prefix}:{{resource}}:{{user_id}}"


def get_rate_limit_config(resource: str) -> RateLimitConfig:
    """Get rate limit configuration for a resource from central settings.
    
    Args:
        resource: Resource name ('question_generate' or 'answer_evaluate')
        
    Returns:
        RateLimitConfig with values from settings
    """
    if resource == "question_generate":
        return RateLimitConfig(
            max_requests=settings.rate_limit_questions_max,
            window_seconds=settings.rate_limit_questions_window,
        )
    elif resource == "answer_evaluate":
        return RateLimitConfig(
            max_requests=settings.rate_limit_evaluations_max,
            window_seconds=settings.rate_limit_evaluations_window,
        )
    elif resource == "multiplayer_game_create":
        return RateLimitConfig(
            max_requests=settings.rate_limit_multiplayer_games_max,
            window_seconds=settings.rate_limit_multiplayer_games_window,
        )
    else:
        # Default fallback
        return RateLimitConfig(
            max_requests=settings.rate_limit_questions_max,
            window_seconds=settings.rate_limit_questions_window,
        )


class RateLimiter:
    """Sliding window rate limiter using Redis."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter with configuration.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config
        self._redis = None
    
    @property
    def redis(self):
        """Lazy-load Redis client."""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis
    
    def _get_key(self, user_id: str, resource: str) -> str:
        """Generate Redis key for rate limiting.
        
        Args:
            user_id: User identifier (user ID or email)
            resource: Resource being rate limited (e.g., 'question_generate')
            
        Returns:
            Redis key string
        """
        return f"{self.config.key_prefix}:{resource}:{user_id}"
    
    def check_rate_limit(
        self, 
        user_id: str, 
        resource: str = "default"
    ) -> Tuple[bool, int, int]:
        """Check if request is within rate limit.
        
        Uses a sliding window counter stored in Redis.
        
        Args:
            user_id: User identifier
            resource: Resource being accessed
            
        Returns:
            Tuple of (allowed: bool, remaining: int, reset_time: int)
            - allowed: Whether the request should be allowed
            - remaining: Number of requests remaining in window
            - reset_time: Unix timestamp when the oldest request expires (limit resets)
        """
        try:
            key = self._get_key(user_id, resource)
            now = time.time()
            window_start = now - self.config.window_seconds
            
            pipe = self.redis.client.pipeline()
            
            # Remove expired entries (outside the window)
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Get the oldest request timestamp (first element)
            pipe.zrange(key, 0, 0, withscores=True)
            
            # Add current request timestamp
            pipe.zadd(key, {str(now): now})
            
            # Set expiry on the key
            pipe.expire(key, self.config.window_seconds)
            
            results = pipe.execute()
            current_count = results[1]  # zcard result
            oldest_entries = results[2]  # zrange result with scores
            
            remaining = max(0, self.config.max_requests - current_count - 1)
            allowed = current_count < self.config.max_requests
            
            # Calculate reset_time based on when the oldest request will expire
            if oldest_entries:
                oldest_timestamp = oldest_entries[0][1]  # Score is the timestamp
                reset_time = int(oldest_timestamp + self.config.window_seconds)
            else:
                reset_time = int(now + self.config.window_seconds)
            
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded user=%s resource=%s count=%d limit=%d reset_at=%d",
                    user_id, resource, current_count, self.config.max_requests, reset_time
                )
                # Remove the request we just added since it's not allowed
                self.redis.client.zrem(key, str(now))
            else:
                logger.debug(
                    "rate_limit_check user=%s resource=%s remaining=%d",
                    user_id, resource, remaining
                )
            
            return allowed, remaining, reset_time
            
        except Exception as e:
            logger.error(
                "rate_limit_check_failed user=%s resource=%s error=%s",
                user_id, resource, e
            )
            # Fail open - allow request if Redis is unavailable
            return True, self.config.max_requests, int(time.time() + self.config.window_seconds)
    
    def get_usage(self, user_id: str, resource: str = "default") -> Tuple[int, int]:
        """Get current usage for a user.
        
        Args:
            user_id: User identifier
            resource: Resource being checked
            
        Returns:
            Tuple of (used: int, limit: int)
        """
        try:
            key = self._get_key(user_id, resource)
            now = time.time()
            window_start = now - self.config.window_seconds
            
            # Clean up and count
            self.redis.client.zremrangebyscore(key, 0, window_start)
            used = self.redis.client.zcard(key)
            
            return used, self.config.max_requests
            
        except Exception as e:
            logger.error("rate_limit_usage_check_failed error=%s", e)
            return 0, self.config.max_requests
    
    def reset(self, user_id: str, resource: str = "default") -> bool:
        """Reset rate limit for a user (admin use).
        
        Args:
            user_id: User identifier
            resource: Resource to reset
            
        Returns:
            True if reset successful
        """
        try:
            key = self._get_key(user_id, resource)
            self.redis.client.delete(key)
            logger.info("rate_limit_reset user=%s resource=%s", user_id, resource)
            return True
        except Exception as e:
            logger.error("rate_limit_reset_failed error=%s", e)
            return False


# Pre-configured limiters
def get_question_limiter() -> RateLimiter:
    """Get rate limiter for question generation."""
    return RateLimiter(get_rate_limit_config("question_generate"))


def get_evaluation_limiter() -> RateLimiter:
    """Get rate limiter for answer evaluation."""
    return RateLimiter(get_rate_limit_config("answer_evaluate"))


def get_multiplayer_game_limiter() -> RateLimiter:
    """Get rate limiter for multiplayer game creation."""
    return RateLimiter(get_rate_limit_config("multiplayer_game_create"))


def get_daily_reset_time() -> int:
    """Calculate next UTC midnight reset time.
    
    Returns:
        Unix timestamp of next UTC midnight
    """
    from datetime import datetime, timezone, timedelta
    
    now = datetime.now(timezone.utc)
    # Get next midnight UTC
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(next_midnight.timestamp())


def check_daily_rate_limit(
    user_id: str,
    resource: str,
    max_requests: int
) -> Tuple[bool, int, int]:
    """Check rate limit with daily reset at UTC midnight.
    
    Args:
        user_id: User identifier
        resource: Resource being rate limited
        max_requests: Maximum requests per day
        
    Returns:
        Tuple of (allowed: bool, remaining: int, reset_time: int)
    """
    try:
        redis_client = get_redis_client()
        now = time.time()
        
        # Calculate start of current UTC day
        from datetime import datetime, timezone
        utc_now = datetime.now(timezone.utc)
        day_start = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_timestamp = day_start.timestamp()
        
        key = f"ratelimit:daily:{resource}:{user_id}"
        
        pipe = redis_client.client.pipeline()
        
        # Remove entries from previous days
        pipe.zremrangebyscore(key, 0, day_start_timestamp)
        
        # Count requests today
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Expire at end of day
        reset_time = get_daily_reset_time()
        pipe.expireat(key, reset_time)
        
        results = pipe.execute()
        current_count = results[1]  # zcard result
        
        remaining = max(0, max_requests - current_count - 1)
        allowed = current_count < max_requests
        
        if not allowed:
            logger.warning(
                "daily_rate_limit_exceeded user=%s resource=%s count=%d limit=%d reset_at_utc_midnight",
                user_id, resource, current_count, max_requests
            )
            # Remove the request we just added since it's not allowed
            redis_client.client.zrem(key, str(now))
        else:
            logger.debug(
                "daily_rate_limit_check user=%s resource=%s remaining=%d",
                user_id, resource, remaining
            )
        
        return allowed, remaining, reset_time
        
    except Exception as e:
        logger.error(
            "daily_rate_limit_check_failed user=%s resource=%s error=%s",
            user_id, resource, e
        )
        # Fail open - allow request if Redis is unavailable
        return True, max_requests, get_daily_reset_time()

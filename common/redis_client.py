"""Redis pub/sub utilities for real-time multiplayer communication.

This module provides a Redis client for pub/sub messaging between the API server
(which handles database operations) and the WebSocket server (which broadcasts
to connected clients).

Architecture:
    API Server → Redis Pub/Sub → WebSocket Server → Clients
    
Channel naming convention:
    - lobby:{code}:events  - Lobby-specific events (player joined, left, ready, etc.)
    - game:{session_id}:events - Game session events (answers, scores, etc.)
    - global:events - System-wide broadcasts
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from enum import Enum

import redis

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for pub/sub messaging."""
    
    # Lobby events
    LOBBY_CREATED = "lobby_created"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    PLAYER_READY = "player_ready"
    LOBBY_UPDATED = "lobby_updated"
    LOBBY_CLOSED = "lobby_closed"
    ALL_PLAYERS_READY = "all_players_ready"
    PLAYER_DISCONNECTED = "player_disconnected"
    SETTINGS_UPDATED = "settings_updated"
    
    # Game events
    GAME_STARTING = "game_starting"
    GAME_STARTED = "game_started"
    QUESTION_SENT = "question_sent"
    ANSWER_SUBMITTED = "answer_submitted"
    ANSWER_RESULT = "answer_result"
    ROUND_ENDED = "round_ended"
    GAME_ENDED = "game_ended"
    SCORES_UPDATED = "scores_updated"
    
    # Chat events
    CHAT_MESSAGE = "chat_message"


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    
    host: str
    port: int
    db: int
    password: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Create config from environment variables."""
        return cls(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            password=os.environ.get("REDIS_PASSWORD"),
        )


class RedisClient:
    """Redis client for pub/sub and temporary state storage.
    
    This client provides:
    - Pub/sub messaging for real-time events
    - Temporary state storage (with TTL) for active lobbies/games
    - Connection pooling for efficient resource usage
    """
    
    def __init__(self, config: Optional[RedisConfig] = None):
        """Initialize Redis client.
        
        Args:
            config: Redis configuration. If None, loads from environment.
        """
        self.config = config or RedisConfig.from_env()
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
    
    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client connection."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=True,
                socket_connect_timeout=2,  # Shorter timeout to avoid blocking
                socket_timeout=2,
                retry_on_timeout=False,  # Don't retry automatically
            )
        return self._client
    
    def ping(self) -> bool:
        """Check Redis connection health."""
        try:
            return self.client.ping()
        except redis.ConnectionError as e:
            logger.error("redis_ping_failed error=%s", e)
            return False
    
    def close(self) -> None:
        """Close Redis connections."""
        if self._pubsub:
            self._pubsub.close()
            self._pubsub = None
        if self._client:
            self._client.close()
            self._client = None
            logger.info("redis_connection_closed")
    
    # ==================== Channel Naming ====================
    
    @staticmethod
    def lobby_channel(lobby_code: str) -> str:
        """Get channel name for lobby events."""
        return f"lobby:{lobby_code.upper()}:events"
    
    @staticmethod
    def game_channel(session_id: str) -> str:
        """Get channel name for game session events."""
        return f"game:{session_id}:events"
    
    @staticmethod
    def global_channel() -> str:
        """Get channel name for global events."""
        return "global:events"
    
    # ==================== Publishing ====================
    
    def publish(self, channel: str, event_type: EventType, data: Dict[str, Any]) -> int:
        """Publish an event to a channel.
        
        Args:
            channel: Channel name to publish to
            event_type: Type of event being published
            data: Event payload data
            
        Returns:
            Number of subscribers that received the message
        """
        message = {
            "type": event_type.value,
            "data": data,
        }
        
        try:
            count = self.client.publish(channel, json.dumps(message))
            logger.debug(
                "redis_event_published channel=%s type=%s subscribers=%d",
                channel, event_type.value, count
            )
            return count
        except redis.RedisError as e:
            logger.error(
                "redis_publish_failed channel=%s type=%s error=%s",
                channel, event_type.value, e
            )
            raise
    
    def publish_lobby_event(
        self, 
        lobby_code: str, 
        event_type: EventType, 
        data: Dict[str, Any]
    ) -> int:
        """Publish an event to a lobby channel.
        
        Args:
            lobby_code: The 6-character lobby code
            event_type: Type of lobby event
            data: Event payload
            
        Returns:
            Number of subscribers
        """
        channel = self.lobby_channel(lobby_code)
        return self.publish(channel, event_type, data)
    
    def publish_game_event(
        self, 
        session_id: str, 
        event_type: EventType, 
        data: Dict[str, Any]
    ) -> int:
        """Publish an event to a game session channel.
        
        Args:
            session_id: The game session ID
            event_type: Type of game event
            data: Event payload
            
        Returns:
            Number of subscribers
        """
        channel = self.game_channel(session_id)
        return self.publish(channel, event_type, data)
    
    # ==================== Subscribing ====================
    
    def subscribe(self, *channels: str) -> redis.client.PubSub:
        """Subscribe to one or more channels.
        
        Args:
            channels: Channel names to subscribe to
            
        Returns:
            PubSub object for receiving messages
        """
        if self._pubsub is None:
            self._pubsub = self.client.pubsub()
        
        self._pubsub.subscribe(*channels)
        logger.info("redis_subscribed channels=%s", channels)
        return self._pubsub
    
    def subscribe_to_lobby(self, lobby_code: str) -> redis.client.PubSub:
        """Subscribe to a lobby's event channel.
        
        Args:
            lobby_code: The 6-character lobby code
            
        Returns:
            PubSub object for receiving messages
        """
        channel = self.lobby_channel(lobby_code)
        return self.subscribe(channel)
    
    def subscribe_to_game(self, session_id: str) -> redis.client.PubSub:
        """Subscribe to a game session's event channel.
        
        Args:
            session_id: The game session ID
            
        Returns:
            PubSub object for receiving messages
        """
        channel = self.game_channel(session_id)
        return self.subscribe(channel)
    
    def listen(self, pubsub: redis.client.PubSub, callback: Callable[[Dict], None]) -> None:
        """Listen for messages on a pubsub connection.
        
        Args:
            pubsub: PubSub object from subscribe()
            callback: Function to call with each message
        """
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    callback(data)
                except json.JSONDecodeError as e:
                    logger.error("redis_message_parse_failed error=%s", e)
    
    # ==================== State Storage ====================
    
    def set_lobby_state(
        self, 
        lobby_code: str, 
        state: Dict[str, Any], 
        ttl_seconds: int = 7200  # 2 hours default
    ) -> bool:
        """Store lobby state in Redis with TTL.
        
        Args:
            lobby_code: The 6-character lobby code
            state: Lobby state dictionary
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        key = f"lobby:{lobby_code.upper()}:state"
        try:
            self.client.setex(key, ttl_seconds, json.dumps(state))
            logger.debug("redis_lobby_state_set lobby=%s ttl=%d", lobby_code, ttl_seconds)
            return True
        except redis.RedisError as e:
            logger.error("redis_set_lobby_state_failed lobby=%s error=%s", lobby_code, e)
            return False
    
    def get_lobby_state(self, lobby_code: str) -> Optional[Dict[str, Any]]:
        """Retrieve lobby state from Redis.
        
        Args:
            lobby_code: The 6-character lobby code
            
        Returns:
            Lobby state dictionary or None if not found
        """
        key = f"lobby:{lobby_code.upper()}:state"
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error("redis_get_lobby_state_failed lobby=%s error=%s", lobby_code, e)
            return None
    
    def delete_lobby_state(self, lobby_code: str) -> bool:
        """Delete lobby state from Redis.
        
        Args:
            lobby_code: The 6-character lobby code
            
        Returns:
            True if deleted, False if not found or error
        """
        key = f"lobby:{lobby_code.upper()}:state"
        try:
            return bool(self.client.delete(key))
        except redis.RedisError as e:
            logger.error("redis_delete_lobby_state_failed lobby=%s error=%s", lobby_code, e)
            return False
    
    def set_game_state(
        self, 
        session_id: str, 
        state: Dict[str, Any], 
        ttl_seconds: int = 3600  # 1 hour default
    ) -> bool:
        """Store game session state in Redis with TTL.
        
        Args:
            session_id: The game session ID
            state: Game state dictionary
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        key = f"game:{session_id}:state"
        try:
            self.client.setex(key, ttl_seconds, json.dumps(state))
            logger.debug("redis_game_state_set session=%s ttl=%d", session_id, ttl_seconds)
            return True
        except redis.RedisError as e:
            logger.error("redis_set_game_state_failed session=%s error=%s", session_id, e)
            return False
    
    def get_game_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve game session state from Redis.
        
        Args:
            session_id: The game session ID
            
        Returns:
            Game state dictionary or None if not found
        """
        key = f"game:{session_id}:state"
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError as e:
            logger.error("redis_get_game_state_failed session=%s error=%s", session_id, e)
            return None


# Singleton instance for convenience
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create the singleton Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def reset_redis_client() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None

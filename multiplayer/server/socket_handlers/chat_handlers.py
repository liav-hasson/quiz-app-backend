"""Socket.IO handlers for chat messages.

Chat is a real-time feature that stays in WebSocket.
Messages are broadcast to the room and optionally published to Redis
for persistence or cross-instance relay.
"""

import logging
from datetime import datetime
from flask import request, current_app
from flask_socketio import emit

from server.utils.auth_middleware import socket_authenticated
from common.redis_client import EventType

logger = logging.getLogger(__name__)


def register_handlers(socketio):
    """Register chat-related Socket.IO event handlers."""

    @socketio.on('send_message')
    @socket_authenticated
    def handle_send_message(user, data):
        """Send a chat message to the lobby.
        
        Expected data: {
            "lobby_code": "ABC123",
            "message": "Hello everyone!"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            message = data.get('message', '').strip()
            
            if not lobby_code:
                emit('error', {'message': 'Lobby code required'})
                return
                
            if not message:
                return  # Silently ignore empty messages
            
            # Limit message length
            if len(message) > 500:
                message = message[:500]
            
            user_id = str(user.get('_id', ''))
            username = user.get('username', 'Anonymous')
            timestamp = datetime.now().isoformat()
            
            # Chat is Redis-only with 2h TTL - no MongoDB persistence needed
            # Messages are stored in Redis lobby state for recent history
            
            message_data = {
                'user_id': user_id,
                'username': username,
                'message': message,
                'timestamp': timestamp
            }
            
            # Publish to Redis - multiplayer subscriber will relay to all clients
            redis_client = current_app.extensions.get('redis_client')
            if redis_client:
                try:
                    redis_client.publish_lobby_event(
                        lobby_code,
                        EventType.CHAT_MESSAGE,
                        message_data
                    )
                    logger.info("chat_message_published_to_redis user=%s lobby=%s msg=%s", username, lobby_code, message[:20])
                    # DO NOT emit here - Redis subscriber will relay it
                except Exception as e:
                    logger.warning("redis_chat_publish_failed error=%s", e)
                    # Fallback: broadcast directly if Redis fails
                    logger.info("chat_message_fallback_direct_emit user=%s lobby=%s", username, lobby_code)
                    emit('new_message', message_data, room=lobby_code)
            else:
                # No Redis - just broadcast locally
                logger.info("chat_message_no_redis_direct_emit user=%s lobby=%s", username, lobby_code)
                emit('new_message', message_data, room=lobby_code)
            
            logger.debug("chat_message user=%s lobby=%s", username, lobby_code)
            
        except Exception as e:
            logger.error("send_message_failed error=%s", e)
            emit('error', {'message': f'Failed to send message: {str(e)}'})

    @socketio.on('typing')
    @socket_authenticated
    def handle_typing(user, data):
        """Broadcast typing indicator to lobby.
        
        Expected data: {
            "lobby_code": "ABC123",
            "is_typing": true
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            is_typing = data.get('is_typing', False)
            
            if not lobby_code:
                return
            
            # Broadcast to room (excluding sender)
            emit('user_typing', {
                'user_id': str(user.get('_id', '')),
                'username': user.get('username', ''),
                'is_typing': is_typing
            }, room=lobby_code, include_self=False)
            
        except Exception as e:
            logger.error("typing_indicator_failed error=%s", e)

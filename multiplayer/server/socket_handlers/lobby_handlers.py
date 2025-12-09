"""Socket.IO handlers for lobby room management.

These handlers manage Socket.IO room membership only.
All lobby state mutations are handled by the API server.
Events are received via Redis pub/sub and relayed to rooms.
"""

import logging
from flask import request, current_app
from flask_socketio import emit, join_room, leave_room, rooms

from server.utils.auth_middleware import socket_authenticated

logger = logging.getLogger(__name__)


def register_handlers(socketio):
    """Register lobby-related Socket.IO event handlers."""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info("client_connected sid=%s", request.sid)
        emit('connected', {'sid': request.sid})

    @socketio.on('join_room')
    @socket_authenticated
    def handle_join_room(user, data):
        """Join a Socket.IO room for a lobby.
        
        This is called AFTER the frontend successfully calls the API to join a lobby.
        The API handles the actual lobby join logic and publishes events.
        This just adds the socket to the room to receive broadcasts.
        
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            
            if not lobby_code:
                emit('error', {'message': 'Lobby code required'})
                return
            
            # Join the Socket.IO room
            join_room(lobby_code)
            
            # Store user info in session for disconnect handling
            request.user = user
            request.lobby_code = lobby_code
            
            logger.info("user_joined_room user=%s room=%s sid=%s", 
                       user.get('username'), lobby_code, request.sid)
            
            # Get recent chat history from Redis/MongoDB
            chat_history = []
            redis_client = current_app.extensions.get('redis_client')
            if redis_client:
                try:
                    # Try to get chat history from Redis cache
                    lobby_state = redis_client.get_lobby_state(lobby_code)
                    if lobby_state and 'chat_messages' in lobby_state:
                        chat_history = lobby_state.get('chat_messages', [])[-50:]
                except Exception as e:
                    logger.warning("redis_chat_history_failed error=%s", e)
            
            # Confirm to client with chat history
            emit('room_joined', {
                'lobby_code': lobby_code,
                'user_id': str(user.get('_id', '')),
                'username': user.get('username', ''),
                'chat_history': chat_history
            })
            
        except Exception as e:
            logger.error("join_room_failed error=%s", e)
            emit('error', {'message': f'Failed to join room: {str(e)}'})

    @socketio.on('leave_room')
    @socket_authenticated
    def handle_leave_room(user, data):
        """Leave a Socket.IO room.
        
        Called when user leaves a lobby (after API call).
        
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            
            if not lobby_code:
                emit('error', {'message': 'Lobby code required'})
                return
            
            # Leave the Socket.IO room
            leave_room(lobby_code)
            
            logger.info("user_left_room user=%s room=%s sid=%s",
                       user.get('username'), lobby_code, request.sid)
            
            # Confirm to client
            emit('room_left', {'lobby_code': lobby_code})
            
        except Exception as e:
            logger.error("leave_room_failed error=%s", e)
            emit('error', {'message': f'Failed to leave room: {str(e)}'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection.
        
        Note: The frontend should call the API's leave endpoint when disconnecting
        intentionally. This handles unexpected disconnects (browser close, network loss).
        """
        try:
            user = getattr(request, 'user', None)
            lobby_code = getattr(request, 'lobby_code', None)
            
            if user and lobby_code:
                logger.info("user_disconnected user=%s room=%s sid=%s",
                           user.get('username'), lobby_code, request.sid)
                
                # Notify room of disconnection
                # Note: The API server should be notified via a separate mechanism
                # (e.g., frontend reconnect logic or heartbeat)
                emit('player_disconnected', {
                    'user_id': str(user.get('_id', '')),
                    'username': user.get('username', '')
                }, room=lobby_code)
            else:
                logger.info("client_disconnected sid=%s", request.sid)
                
        except Exception as e:
            logger.error("disconnect_handler_error error=%s", e)

    @socketio.on('ping_lobby')
    @socket_authenticated
    def handle_ping_lobby(user, data):
        """Heartbeat to confirm user is still in lobby.
        
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        lobby_code = data.get('lobby_code', '').upper()
        if lobby_code:
            emit('pong_lobby', {
                'lobby_code': lobby_code,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            })


    # =========================================================================
    # Legacy event handlers for backwards compatibility
    # These redirect clients to use the new REST API + room pattern
    # =========================================================================

    @socketio.on('create_lobby')
    @socket_authenticated
    def handle_create_lobby_legacy(user, data):
        """Legacy handler - tells client to use REST API instead."""
        emit('error', {
            'message': 'Please use the REST API to create a lobby, then join_room',
            'code': 'USE_REST_API'
        })

    @socketio.on('join_lobby')
    @socket_authenticated  
    def handle_join_lobby_legacy(user, data):
        """Legacy handler - tells client to use REST API instead."""
        emit('error', {
            'message': 'Please use the REST API to join a lobby, then join_room',
            'code': 'USE_REST_API'
        })

    @socketio.on('toggle_ready')
    @socket_authenticated
    def handle_toggle_ready_legacy(user, data):
        """Legacy handler - tells client to use REST API instead."""
        emit('error', {
            'message': 'Please use the REST API to toggle ready status',
            'code': 'USE_REST_API'
        })

    @socketio.on('leave_lobby')
    @socket_authenticated
    def handle_leave_lobby_legacy(user, data):
        """Legacy handler - tells client to use REST API instead."""
        emit('error', {
            'message': 'Please use the REST API to leave the lobby, then leave_room',
            'code': 'USE_REST_API'
        })

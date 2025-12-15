"""WebSocket server application - Redis-based event relay.

This module provides the Flask-SocketIO application for real-time multiplayer.
It does NOT access MongoDB directly - all state is managed via:
1. Redis pub/sub for events from API server
2. Redis state storage for temporary lobby/game state
3. Socket.IO rooms for broadcasting to clients

Architecture:
    API Server → Redis Pub/Sub → This Server → Socket.IO → Clients

NOTE: Eventlet monkey patching is done in wsgi.py entry point
"""

import logging
import threading

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from prometheus_flask_exporter import PrometheusMetrics

from common.utils.config import settings
from common.redis_client import get_redis_client
from common.utils.identity.token_service import TokenService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize SocketIO globally for handler access
socketio = SocketIO()

# Redis subscriber thread reference
_redis_subscriber_thread = None


def create_app():
    """Application factory for the WebSocket server."""
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": settings.websocket_cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # Build Redis message queue URL for Socket.IO scaling
    # NOTE: Disabled for single-instance deployment to avoid Redis message queue errors
    # For multi-instance horizontal scaling, uncomment and ensure Redis is properly configured
    redis_url = None
    # if settings.redis_host:
    #     redis_url = f'redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}'
    #     logger.info("socketio_redis_message_queue url=%s", redis_url)
    
    # Initialize SocketIO without Redis message queue (single instance mode)
    socketio.init_app(
        app,
        cors_allowed_origins=settings.websocket_cors_origins,
        async_mode='eventlet',
        message_queue=None,  # Use in-memory pub/sub for single instance
        ping_interval=settings.websocket_ping_interval,
        ping_timeout=settings.websocket_ping_timeout,
        logger=True,
        engineio_logger=True
    )
    
    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(app)
    metrics.info("multiplayer_server_info", "Multiplayer WebSocket Server", version="2.0.0")
    
    # Initialize services
    token_service = TokenService()
    
    # Store dependencies in app.extensions
    app.extensions['token_service'] = token_service
    app.extensions['socketio'] = socketio
    
    logger.info("multiplayer_server_initialized")
    
    # Initialize Redis client and store in extensions (non-blocking)
    redis_client = get_redis_client()
    try:
        # Quick ping with short timeout - don't block if Redis isn't ready yet
        if redis_client.ping():
            app.extensions['redis_client'] = redis_client
            logger.info("redis_connected host=%s port=%s", settings.redis_host, settings.redis_port)
        else:
            logger.warning("redis_ping_failed - continuing without Redis state")
            app.extensions['redis_client'] = None
    except Exception as e:
        # Redis not ready yet - that's ok, subscriber will retry
        logger.warning("redis_initial_connection_failed error=%s - subscriber will retry", e)
        app.extensions['redis_client'] = None
    
    # Register health routes
    from routes.health_routes import init_health_routes
    app.register_blueprint(init_health_routes())
    
    # Register Socket.IO event handlers (new handlers without MongoDB)
    from socket_handlers import lobby_handlers, game_handlers, chat_handlers
    lobby_handlers.register_handlers(socketio)
    game_handlers.register_handlers(socketio)
    chat_handlers.register_handlers(socketio)
    
    # Always start Redis subscriber - it will retry if Redis is not ready yet
    # This ensures events flow from API server even if Redis isn't available during startup
    start_redis_subscriber(app, socketio)
    
    logger.info("multiplayer_websocket_server_initialized")
    return app


def start_redis_subscriber(app, sio):
    """Start background thread to subscribe to Redis events and relay to Socket.IO.
    
    This subscribes to pattern 'lobby:*:events' and 'game:*:events' channels
    and broadcasts received events to the appropriate Socket.IO rooms.
    """
    global _redis_subscriber_thread
    
    def subscriber_loop():
        """Background loop that listens for Redis pub/sub messages."""
        import json
        import redis
        import time
        
        logger.info("redis_subscriber_starting")
        
        # Use settings from config (reads from environment variables)
        # K8s service discovery works via DNS: redis.namespace.svc.cluster.local
        redis_host = settings.redis_host or 'redis'
        redis_port = settings.redis_port
        logger.info("redis_connecting host=%s port=%d", redis_host, redis_port)
        
        # Retry logic for initial connection
        max_retries = 10
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                logger.info("redis_subscriber_connecting attempt=%d/%d host=%s", attempt + 1, max_retries, redis_host)
                
                # Create a separate Redis connection for subscribing
                redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=None,
                    socket_keepalive=True,
                    health_check_interval=30
                )
                
                # Test connection
                redis_client.ping()
                logger.info("redis_subscriber_connected")
                
                pubsub = redis_client.pubsub()
                
                # Subscribe to lobby and game event patterns
                pubsub.psubscribe('lobby:*:events', 'game:*:events')
                logger.info("redis_subscribed patterns=['lobby:*:events', 'game:*:events']")
                
                # Main event loop
                for message in pubsub.listen():
                    if message['type'] == 'pmessage':
                        try:
                            channel = message['channel']
                            data = json.loads(message['data'])
                            
                            # Extract room from channel (lobby:ABC123:events → ABC123)
                            parts = channel.split(':')
                            if len(parts) >= 2:
                                room = parts[1]  # The lobby code or game session ID
                                event_type = data.get('type')
                                event_data = data.get('data', {})
                                
                                # Relay to Socket.IO room
                                logger.info("redis_relay event=%s room=%s", event_type, room)
                                with app.app_context():
                                    relay_event_to_room(sio, room, event_type, event_data)
                                    
                        except json.JSONDecodeError as e:
                            logger.error("redis_message_parse_error error=%s", e)
                        except Exception as e:
                            logger.error("redis_relay_error error=%s", e)
                
                # If we exit the listen loop, connection was closed
                logger.warning("redis_subscriber_disconnected - retrying in %ds", retry_delay)
                time.sleep(retry_delay)
                            
            except redis.ConnectionError as e:
                logger.warning("redis_subscriber_connection_failed attempt=%d/%d error=%s - retrying in %ds", 
                             attempt + 1, max_retries, e, retry_delay)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("redis_subscriber_failed_all_attempts - giving up")
                    break
            except Exception as e:
                logger.error("redis_subscriber_unexpected_error error=%s", e, exc_info=True)
                break
    
    # Start subscriber in background thread
    _redis_subscriber_thread = threading.Thread(target=subscriber_loop, daemon=True)
    _redis_subscriber_thread.start()
    logger.info("redis_subscriber_thread_started")


def relay_event_to_room(sio, room, event_type, event_data):
    """Relay a Redis event to a Socket.IO room.
    
    Maps Redis event types to Socket.IO event names.
    Special handling for GAME_STARTING to trigger countdown and game initialization.
    """
    # Map event types to Socket.IO event names
    event_mapping = {
        # Lobby events
        'lobby_created': 'lobby_created',
        'player_joined': 'player_joined',
        'player_left': 'player_left',
        'player_ready': 'player_ready',
        'lobby_updated': 'lobby_updated',
        'lobby_closed': 'lobby_closed',
        'all_players_ready': 'all_players_ready',
        'player_disconnected': 'player_disconnected',
        'settings_updated': 'settings_updated',
        
        # Game events
        'game_starting': 'countdown_started',
        'game_started': 'game_started',
        'question_sent': 'question_started',
        'answer_result': 'answer_recorded',
        'round_ended': 'question_ended',
        'game_ended': 'game_ended',
        'scores_updated': 'scores_updated',
        
        # Chat events
        'chat_message': 'new_message',
    }
    
    socket_event = event_mapping.get(event_type, event_type)
    
    # Special handling for game_starting - trigger countdown and game initialization
    if event_type == 'game_starting':
        from socket_handlers.game_events import start_game_with_countdown
        from flask import current_app
        
        countdown_seconds = event_data.get('countdown_seconds', 3)
        lobby_data = event_data.get('lobby', {})
        lobby_code = lobby_data.get('lobby_code', room)
        
        # Extract question_list from lobby data (primary source)
        question_list = lobby_data.get('question_list', [])
        question_timer = lobby_data['question_timer']  # No fallback - lobby must have this
        
        # Extract AI settings if provided (for user-provided API key)
        ai_settings = event_data.get('ai_settings')
        
        logger.info("game_starting_received lobby=%s countdown=%d questions=%d timer=%d has_ai_key=%s", 
                   lobby_code, countdown_seconds, len(question_list), question_timer,
                   "yes" if ai_settings and ai_settings.get('api_key') else "no")
        
        # Start background task for countdown and game initialization
        sio.start_background_task(
            start_game_with_countdown,
            sio,
            current_app._get_current_object(),
            lobby_code,
            countdown_seconds,
            question_list,
            question_timer,
            ai_settings
        )
        return  # Don't emit twice - countdown handler will emit
    
    # Special handling for chat_message - store in Redis and broadcast
    if event_type == 'chat_message':
        from flask import current_app
        redis_client = current_app.extensions.get('redis_client')
        if redis_client:
            try:
                # Get existing chat history
                lobby_state = redis_client.get_lobby_state(room) or {}
                chat_messages = lobby_state.get('chat_messages', [])
                
                # Add new message
                chat_messages.append(event_data)
                
                # Keep only last 50 messages
                chat_messages = chat_messages[-50:]
                
                # Update lobby state with new chat history
                lobby_state['chat_messages'] = chat_messages
                redis_client.set_lobby_state(room, lobby_state, ttl_seconds=7200)  # 2 hours
                
                logger.debug("chat_message_persisted lobby=%s total=%d", room, len(chat_messages))
            except Exception as e:
                logger.warning("chat_persist_failed lobby=%s error=%s", room, e)
    
    logger.debug("relay_event room=%s type=%s socket_event=%s", room, event_type, socket_event)
    sio.emit(socket_event, event_data, room=room, namespace='/')


if __name__ == '__main__':
    app = create_app()
    logger.info("=" * 60)
    logger.info("Starting Multiplayer WebSocket Server on %s:%s", settings.host, settings.port)
    logger.info("=" * 60)
    socketio.run(app, host=settings.host, port=settings.port)

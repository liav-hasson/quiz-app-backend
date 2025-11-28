import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from prometheus_flask_exporter import PrometheusMetrics

from common.utils.config import settings
from common.database import DBController
from server.models.repositories.lobby_repository import LobbyRepository
from server.models.repositories.game_session_repository import GameSessionRepository
from common.repositories.user_repository import UserRepository
from common.repositories.quiz_repository import QuizRepository
from common.repositories.questions_repository import QuestionsRepository
from server.models.repositories.multiplayer_xp_repository import MultiplayerXPRepository
from common.utils.identity.token_service import TokenService
from server.controllers.lobby_controller import LobbyController
from server.controllers.game_controller import GameController

# Initialize SocketIO
socketio = SocketIO()

def create_app():
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
    
    # Initialize SocketIO
    socketio.init_app(
        app,
        cors_allowed_origins=settings.websocket_cors_origins,
        async_mode='eventlet',
        message_queue=f'redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}' if settings.redis_host else None,
        ping_interval=settings.websocket_ping_interval,
        ping_timeout=settings.websocket_ping_timeout
    )
    
    # Initialize Metrics
    metrics = PrometheusMetrics(app)
    
    # Initialize Database
    db_controller = DBController()
    db_controller.connect()
    
    # Initialize Repositories
    user_repository = UserRepository(db_controller)
    questions_repository = QuestionsRepository(db_controller)
    quiz_repository = QuizRepository(db_controller)
    lobby_repository = LobbyRepository(db_controller)
    game_session_repository = GameSessionRepository(db_controller, questions_repository, quiz_repository)
    multiplayer_xp_repository = MultiplayerXPRepository(user_repository)
    
    # Initialize Services
    token_service = TokenService()
    
    # Initialize Controllers
    lobby_controller = LobbyController(lobby_repository, quiz_repository)
    game_controller = GameController(game_session_repository, lobby_repository, multiplayer_xp_repository)
    
    # Store dependencies
    app.extensions['db_controller'] = db_controller
    app.extensions['user_repository'] = user_repository
    app.extensions['lobby_repository'] = lobby_repository
    app.extensions['game_session_repository'] = game_session_repository
    app.extensions['token_service'] = token_service
    app.extensions['lobby_controller'] = lobby_controller
    app.extensions['game_controller'] = game_controller
    
    # Register Blueprints
    from server.routes.health_routes import init_health_routes
    from server.routes.lobby_routes import init_lobby_routes
    app.register_blueprint(init_health_routes())
    app.register_blueprint(init_lobby_routes(lobby_controller))
    
    # Register SocketIO Handlers
    from server.socket_handlers import lobby_events, game_events, chat_events
    lobby_events.register_handlers(socketio)
    game_events.register_handlers(socketio)
    chat_events.register_handlers(socketio)
    
    return app, socketio

if __name__ == '__main__':
    app, socketio = create_app()
    socketio.run(app, host=settings.host, port=settings.port)

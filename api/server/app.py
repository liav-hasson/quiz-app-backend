"""Quiz app REST API - Main application entry point.

This module provides the Flask application factory and initialization logic
for the Quiz App backend API. It handles:
- Database connection and controller initialization
- OAuth configuration for Google authentication
- Route registration and middleware setup
- Prometheus metrics configuration
"""

import logging
import os
import sys
import time
from typing import Callable, Optional

from authlib.integrations.flask_client import OAuth
from flask import Flask, current_app, g, request, jsonify
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics

try:  # pragma: no cover - optional dependency (dev/test envs)
    from prometheus_client import Gauge
except ImportError:  # pragma: no cover - fallback when library missing
    Gauge = None  # type: ignore

# Configuration
from common.utils.config import settings

# Database and repositories
from common.database import DBController
from common.repositories.user_repository import UserRepository
from common.repositories.questions_repository import QuestionsRepository
from common.repositories.leaderboard_repository import LeaderboardRepository
from common.repositories.quiz_repository import QuizRepository
from common.repositories.lobby_repository import LobbyRepository
from models.data_migrator import DataMigrator
from common.utils.identity import TokenService, GoogleTokenVerifier

# Routes
from routes.health_routes import health_bp, init_health_routes
from routes.quiz_routes import quiz_bp, init_quiz_routes
from routes.auth_routes import auth_bp, init_auth_routes
from routes.user_activity_routes import user_activity_bp, init_user_activity_routes
from routes.multiplayer_routes import multiplayer_bp, init_multiplayer_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def initialize_database(app: Flask) -> bool:
    """Initialize database connection and verify data exists.

    Args:
        app: Flask application instance to store dependencies.

    Returns:
        bool: True if initialization successful, False otherwise.
    """
    try:
        logger.info("Connecting to MongoDB...")
        db_controller = DBController()

        if not db_controller.connect():
            logger.error("Failed to connect to MongoDB")
            return False

        # Initialize repositories
        quiz_repository = QuizRepository(db_controller)
        user_repository = UserRepository(db_controller)
        questions_repository = QuestionsRepository(db_controller)
        leaderboard_repository = LeaderboardRepository(db_controller)
        lobby_repository = LobbyRepository(db_controller)

        # Ensure MongoDB indexes are created for lobbies
        # This creates: unique index on lobby_code, TTL index on expire_at
        lobby_repository.ensure_indexes()
        logger.info("Lobby indexes ensured")

        # Identity helpers
        token_service = TokenService()
        google_token_verifier = GoogleTokenVerifier()

        # Initialize OAuth
        try:
            oauth = OAuth()
            oauth.init_app(app)
            oauth.register(
                name="google",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                server_metadata_url=(
                    "https://accounts.google.com/.well-known/openid-configuration"
                ),
                client_kwargs={"scope": "openid email profile"},
            )
            logger.info("OAuth initialized successfully")
        except Exception as exc:
            logger.error("OAuth initialization failed: %s", str(exc), exc_info=True)
            raise RuntimeError(f"Failed to initialize OAuth: {exc}") from exc

        # Check if quiz data exists
        topics = quiz_repository.get_all_topics()

        if not topics:
            auto_migrate = os.getenv("AUTO_MIGRATE_DB", "true").lower() == "true"

            if auto_migrate:
                logger.warning("No quiz data found in MongoDB, attempting migration...")
                json_path = os.path.join(os.path.dirname(__file__), "models", "db.json")

                if os.path.exists(json_path):
                    migrator = DataMigrator(db_controller, quiz_repository)
                    if migrator.migrate_from_json_file(json_path):
                        logger.info("Data migration successful")
                        topics = quiz_repository.get_all_topics()
                    else:
                        logger.error("Data migration failed")
                        return False
                else:
                    logger.error("db.json not found at %s", json_path)
                    return False
            else:
                logger.error("No quiz data found and AUTO_MIGRATE_DB is disabled")
                return False

        # Store all dependencies in app.extensions for thread-safe access
        app.extensions["db_controller"] = db_controller
        app.extensions["quiz_repository"] = quiz_repository
        app.extensions["user_repository"] = user_repository
        app.extensions["questions_repository"] = questions_repository
        app.extensions["leaderboard_repository"] = leaderboard_repository
        app.extensions["lobby_repository"] = lobby_repository
        app.extensions["token_service"] = token_service
        app.extensions["google_token_verifier"] = google_token_verifier
        app.extensions["oauth"] = oauth

        logger.info("Database initialized successfully. Available topics: %s", topics)
        return True

    except (ConnectionError, RuntimeError, OSError) as exc:
        logger.error("Database initialization failed: %s", str(exc), exc_info=True)
        return False


def initialize_routes(app: Flask) -> None:
    """Initialize and register all route blueprints.

    Args:
        app: Flask application instance containing initialized dependencies.
    """
    # Get dependencies from app extensions
    db_controller = app.extensions["db_controller"]
    quiz_repository = app.extensions["quiz_repository"]
    user_repository = app.extensions["user_repository"]
    questions_repository = app.extensions["questions_repository"]
    leaderboard_repository = app.extensions["leaderboard_repository"]
    token_service = app.extensions["token_service"]
    google_token_verifier = app.extensions["google_token_verifier"]
    oauth = app.extensions["oauth"]
    dependency_metric_setter = app.extensions.get("dependency_metric_setter")

    # Initialize route dependencies
    init_health_routes(
        db_controller,
        google_verifier_param=google_token_verifier,
        dependency_metric_callback_param=dependency_metric_setter,
    )
    init_quiz_routes(quiz_repository)

    # Initialize user activity routes first to get the controller
    user_activity_controller = init_user_activity_routes(
        user_repository, questions_repository, leaderboard_repository
    )

    # Pass user_activity_controller to auth routes for streak checking on login
    init_auth_routes(
        oauth,
        user_repository,
        token_service,
        google_token_verifier,
        user_activity_controller,
    )

    # Initialize multiplayer routes
    lobby_repository = app.extensions["lobby_repository"]
    init_multiplayer_routes(lobby_repository, quiz_repository)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_activity_bp)
    app.register_blueprint(multiplayer_bp)

    logger.info("All routes registered successfully")


def setup_middleware(app: Flask) -> None:
    """Setup Flask middleware and request hooks.

    Args:
        app: Flask application instance containing initialized dependencies.
    """

    @app.before_request
    def authenticate_request() -> Optional[tuple]:
        """Authenticate requests using JWT Bearer tokens."""
        # Avoid leaking request paths in production logs
        if app.debug:
            print(
                f"DEBUG: authenticate_request method={request.method} path={request.path}",
                flush=True,
            )

        # Always allow OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return None

        exempt_paths = (
            "/api/health",
            "/api/auth/",
            "/metrics",
            "/api/categories",
            "/api/subjects",
            "/api/all-subjects",
            "/api/multiplayer/game-session/create",  # Internal service-to-service (has X-Internal-Secret check)
            "/api/multiplayer/game-action/",  # Internal game action endpoints (has X-Internal-Secret check)
        )

        if current_app.config.get("TESTING"):
            return None

        require_auth = current_app.config.get("REQUIRE_AUTHENTICATION", True)
        logger.info("auth_middleware_check path=%s require_auth=%s", request.path, require_auth)
        
        if not require_auth:
            return None

        if any(request.path.startswith(path) for path in exempt_paths):
            logger.info("auth_middleware_exempt path=%s", request.path)
            return None

        # Special exemption for GET /api/multiplayer/lobby/<id> (Public details)
        # But POST/PUT/PATCH to /api/multiplayer/lobby/... must be authenticated
        if request.path.startswith("/api/multiplayer/lobby/") and request.method == "GET":
             logger.info("auth_middleware_exempt_lobby_get path=%s", request.path)
             return None

        # Get dependencies from app extensions (thread-safe)
        user_repository = current_app.extensions.get("user_repository")
        token_service = current_app.extensions.get("token_service")

        if not user_repository:
            logger.error("user_repository_not_initialized")
            return jsonify({"error": "Service not properly initialized"}), 503

        if not token_service:
            logger.error("token_service_not_initialized")
            return jsonify({"error": "Authentication unavailable"}), 503

        # Extract JWT from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            logger.warning("missing_bearer_token path=%s", request.path)
            return jsonify({"error": "Authentication required"}), 401

        bearer_token = auth_header.split(" ", 1)[1].strip()

        # Validate JWT and extract claims
        try:
            claims = token_service.decode(bearer_token)
            email = claims.get("email")
            if not email:
                logger.warning("jwt_missing_email_claim")
                return jsonify({"error": "Invalid token: missing email claim"}), 401
        except Exception as exc:  # pragma: no cover - jwt lib raises many types
            logger.warning("jwt_invalid_token path=%s error=%s", request.path, exc)
            return jsonify({"error": "Invalid or expired token"}), 401

        try:
            user = user_repository.get_user_by_email(email)
            if not user:
                logger.warning("user_not_found_for_email email=%s", email)
                return jsonify({"error": "User not found. Please login first."}), 404

            g.user = user
            g.user_email = email
            g.user_claims = claims or {}
            logger.debug(
                "user_authenticated email=%s user_id=%s", email, user.get("_id")
            )
        except Exception as exc:
            logger.error(
                "authentication_failed email=%s error=%s",
                email,
                str(exc),
                exc_info=True,
            )
            return jsonify({"error": "Failed to authenticate user"}), 500

        return None

    @app.before_request
    def before_request() -> None:
        """Log request start and track timing."""
        g.start_time = time.time()
        logger.info(
            "request_started method=%s path=%s remote_addr=%s",
            request.method,
            request.path,
            request.remote_addr,
        )

    @app.after_request
    def after_request(response):
        """Log request completion with duration.

        Args:
            response: Flask response object.

        Returns:
            Flask response object.
        """
        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            logger.info(
                "request_completed method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.path,
                response.status_code,
                duration * 1000,
            )
        return response


def setup_metrics(app: Flask) -> None:
    """Setup Prometheus metrics and dependency gauges.

    Args:
        app: Flask application instance to store metric setter.
    """
    metrics = PrometheusMetrics(app)
    metrics.info("quiz_app_info", "Quiz Application Info", version="1.0.0")

    if Gauge is not None:
        dependency_gauge = Gauge(
            "quiz_dependency_health",
            "Health status for external dependencies (1=up, 0=down)",
            ["dependency"],
        )

        def _set_dependency_metric(dependency: str, healthy: bool) -> None:
            dependency_gauge.labels(dependency=dependency).set(1 if healthy else 0)

        # Store in app extensions (thread-safe)
        app.extensions["dependency_metric_setter"] = _set_dependency_metric
    else:
        logger.warning(
            "prometheus_client_missing", extra={"dependency": "prometheus_client"}
        )
        app.extensions["dependency_metric_setter"] = None
    logger.info("Prometheus metrics initialized")


def create_app() -> Flask:
    """Application factory pattern.

    Returns:
        Flask: Configured Flask application instance.
    """
    # Create Flask app instance
    app = Flask(__name__)
    app.config["REQUIRE_AUTHENTICATION"] = settings.require_authentication
    
    # Enable CORS for cross-origin requests
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-OpenAI-API-Key", "X-OpenAI-Model"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    logger.info("CORS enabled for API endpoints")
    
    # Initialize database and store dependencies in app.extensions
    if not initialize_database(app):
        logger.critical("Cannot start app without database connection")
        sys.exit(1)

    # Setup middleware (uses app.extensions)
    setup_middleware(app)

    # Setup metrics (stores in app.extensions)
    setup_metrics(app)

    # Initialize routes (reads from app.extensions)
    initialize_routes(app)

    logger.info("Application created successfully")
    return app


if __name__ == "__main__":
    # Create and configure app
    application = create_app()

    logger.info("=" * 60)
    logger.info("Starting Flask app on %s:%s", settings.host, settings.port)
    logger.info("=" * 60)

    application.run(debug=settings.debug, host=settings.host, port=settings.port)

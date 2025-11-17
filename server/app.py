"""Quiz app REST API - Main application entry point."""

from flask import Flask, g, request
import logging
import time
import sys
import os
from typing import Optional
from prometheus_flask_exporter import PrometheusMetrics

# Configuration
from utils.config import Config

# Database models
from models.dbcontroller import DBController
from models.user_controller import UserController
from models.questions_controller import QuestionsController
from models.topten_controller import TopTenController
from models.quiz_controller import QuizController
from models.migrator import DataMigrator

# Routes
from routes.health_routes import health_bp, init_health_routes
from routes.quiz_routes import quiz_bp
from routes.auth_routes import auth_bp, init_auth_routes
from routes.user_activity_routes import user_activity_bp, init_user_activity_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Database controllers (initialized later)
db_controller: Optional[DBController] = None
user_controller: Optional[UserController] = None
questions_controller: Optional[QuestionsController] = None
toptens_controller: Optional[TopTenController] = None
quiz_controller: Optional[QuizController] = None
oauth = None  # type: ignore


def initialize_database():
    """Initialize database connection and verify data exists."""
    global db_controller, quiz_controller
    global user_controller, questions_controller, toptens_controller, oauth

    try:
        logger.info("Connecting to MongoDB...")
        db_controller = DBController()

        if not db_controller.connect():
            logger.error("Failed to connect to MongoDB")
            return False

        # Initialize controllers
        quiz_controller = QuizController(db_controller)
        user_controller = UserController(db_controller)
        questions_controller = QuestionsController(db_controller)
        toptens_controller = TopTenController(db_controller)

        # Initialize OAuth
        try:
            from authlib.integrations.flask_client import OAuth

            oauth = OAuth()
            oauth.init_app(app)
            oauth.register(
                name="google",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
            logger.info("OAuth initialized successfully")
        except Exception as e:
            logger.error("OAuth initialization failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Failed to initialize OAuth: {e}")

        # Check if quiz data exists
        topics = quiz_controller.get_all_topics()

        if not topics:
            auto_migrate = os.getenv("AUTO_MIGRATE_DB", "true").lower() == "true"

            if auto_migrate:
                logger.warning("No quiz data found in MongoDB, attempting migration...")
                json_path = os.path.join(os.path.dirname(__file__), "models", "db.json")

                if os.path.exists(json_path):
                    migrator = DataMigrator(db_controller, quiz_controller)
                    if migrator.migrate_from_json_file(json_path):
                        logger.info("Data migration successful")
                        topics = quiz_controller.get_all_topics()
                    else:
                        logger.error("Data migration failed")
                        return False
                else:
                    logger.error("db.json not found at %s", json_path)
                    return False
            else:
                logger.error("No quiz data found and AUTO_MIGRATE_DB is disabled")
                return False

        logger.info("Database initialized successfully. Available topics: %s", topics)
        return True

    except Exception as e:
        logger.error("Database initialization failed: %s", str(e), exc_info=True)
        return False


def initialize_routes():
    """Initialize and register all route blueprints."""
    # Initialize route dependencies
    init_health_routes(db_controller)
    init_auth_routes(oauth, user_controller)
    init_user_activity_routes(user_controller, questions_controller, toptens_controller)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_activity_bp)

    logger.info("All routes registered successfully")


def setup_middleware():
    """Setup Flask middleware and request hooks."""

    @app.before_request
    def before_request():
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
        """Log request completion with duration."""
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


def setup_metrics():
    """Setup Prometheus metrics."""
    metrics = PrometheusMetrics(app)
    metrics.info("quiz_app_info", "Quiz Application Info", version="1.0.0")
    logger.info("Prometheus metrics initialized")


def create_app():
    """Application factory pattern."""
    # Initialize database
    if not initialize_database():
        logger.critical("Cannot start app without database connection")
        sys.exit(1)

    # Setup middleware
    setup_middleware()

    # Setup metrics
    setup_metrics()

    # Initialize routes
    initialize_routes()

    logger.info("Application created successfully")
    return app


if __name__ == "__main__":
    # Create and configure app
    application = create_app()

    logger.info("=" * 60)
    logger.info("Starting Flask app on %s:%s", Config.HOST, Config.PORT)
    logger.info("=" * 60)

    application.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)

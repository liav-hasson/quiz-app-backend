"""Pytest configuration and fixtures for multiplayer server tests."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest


# Ensure server modules are importable
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_path not in sys.path:
    sys.path.insert(0, src_path)


@pytest.fixture
def app():
    """Create application instance for testing.
    
    Mocks SocketIO and Redis to avoid async_mode issues in tests.
    """
    from flask import Flask
    from flask_cors import CORS
    from routes.health_routes import init_health_routes
    
    # Create a minimal test Flask app without SocketIO/eventlet
    test_app = Flask(__name__)
    test_app.config['TESTING'] = True
    
    CORS(test_app)
    
    # Mock extensions
    test_app.extensions = {
        'token_service': MagicMock(),
        'socketio': MagicMock(),
        'redis_client': None,  # Simulate Redis not connected
    }
    
    # Register health routes
    test_app.register_blueprint(init_health_routes())
    
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

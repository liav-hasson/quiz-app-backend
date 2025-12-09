"""WSGI entry point for the multiplayer server.

This module MUST be the entry point for gunicorn to ensure eventlet
monkey patching happens before any other imports.
"""

# CRITICAL: Monkey-patch FIRST, before ANY other imports
import eventlet
eventlet.monkey_patch()

# Now safe to import the app
from server.app import create_app

# Create the app instance for gunicorn
app = create_app()

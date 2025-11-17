"""Health check routes."""

import logging
from flask import Blueprint, jsonify
from typing import Optional

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api")

# Will be set by main.py
db_controller = None


def init_health_routes(db_ctrl):
    """Initialize health routes with database controller."""
    global db_controller
    db_controller = db_ctrl


@health_bp.route("/health")
def health():
    """Health check endpoint."""
    logger.debug("health_check_called")

    db_status = (
        "connected"
        if db_controller and db_controller.db is not None
        else "disconnected"
    )

    return jsonify({"status": "ok", "database": db_status})

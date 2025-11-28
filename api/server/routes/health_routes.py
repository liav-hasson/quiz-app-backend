"""Health check routes with dependency diagnostics."""

import logging
import os
from typing import Callable, Optional, Tuple

from flask import Blueprint, jsonify

from common.utils.config import settings

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api")

# Will be set by app factory
db_controller = None
google_verifier_ref = None
dependency_metric_callback: Optional[Callable[[str, bool], None]] = None


def init_health_routes(
    db_ctrl,
    google_verifier_param=None,
    dependency_metric_callback_param: Optional[Callable[[str, bool], None]] = None,
):
    """Initialize health routes with injected dependencies."""

    global db_controller, google_verifier_ref
    global dependency_metric_callback

    db_controller = db_ctrl
    google_verifier_ref = google_verifier_param
    dependency_metric_callback = dependency_metric_callback_param


def _record_metric(dependency: str, healthy: bool) -> None:
    if dependency_metric_callback:
        dependency_metric_callback(dependency, healthy)


def _check_database() -> Tuple[bool, str]:
    if not db_controller:
        return False, "db_controller_not_initialized"

    db = getattr(db_controller, "db", None)
    if db is None:
        return False, "disconnected"

    client = getattr(db_controller, "client", None)
    if client is None:
        return True, "connected_no_client"

    try:
        client.admin.command("ping")
        return True, "connected"
    except Exception as exc:  # pragma: no cover - relies on Mongo client
        logger.warning("database_ping_failed error=%s", str(exc))
        return False, "ping_failed"


def _check_ai_provider() -> Tuple[bool, str]:
    if settings.openai_api_key:
        return True, "api_key_present"
    if settings.openai_ssm_parameter_name:
        return True, "ssm_parameter_configured"
    return False, "missing_openai_credentials"


def _check_oauth() -> Tuple[bool, str]:
    if not google_verifier_ref:
        return False, "verifier_not_initialized"
    if os.environ.get("GOOGLE_CLIENT_ID"):
        return True, "env_client_id"
    if settings.google_client_id_parameter:
        return True, "ssm_parameter_configured"
    return False, "missing_google_client_id"


@health_bp.route("/health")
def health():
    """Health check endpoint."""
    logger.debug("health_check_called")

    dependency_results = {
        "database": _check_database(),
        "ai_provider": _check_ai_provider(),
        "oauth": _check_oauth(),
    }

    overall_healthy = True
    for dependency, (healthy, _details) in dependency_results.items():
        overall_healthy = overall_healthy and healthy
        _record_metric(dependency, healthy)

    response = {
        "status": "ok" if overall_healthy else "degraded",
        "dependencies": {
            name: {"healthy": healthy, "details": details}
            for name, (healthy, details) in dependency_results.items()
        },
    }

    return jsonify(response)

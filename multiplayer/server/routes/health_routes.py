"""Health check routes for the multiplayer WebSocket server."""

from flask import Blueprint, jsonify, current_app


def init_health_routes():
    """Initialize health check routes."""
    health_bp = Blueprint('health', __name__)
    
    @health_bp.route('/api/health', methods=['GET'])
    def health_check():
        """Basic health check - always returns healthy if server is running."""
        return jsonify({
            'status': 'healthy',
            'service': 'quiz-multiplayer',
            'version': '2.0.0'
        }), 200
    
    @health_bp.route('/api/health/ready', methods=['GET'])
    def readiness_check():
        """Readiness check - verifies Redis connection."""
        redis_client = current_app.extensions.get('redis_client')
        
        redis_ok = False
        if redis_client:
            try:
                redis_ok = redis_client.ping()
            except Exception:
                redis_ok = False
        
        if redis_ok:
            return jsonify({
                'status': 'ready',
                'service': 'quiz-multiplayer',
                'redis': 'connected'
            }), 200
        else:
            return jsonify({
                'status': 'degraded',
                'service': 'quiz-multiplayer',
                'redis': 'disconnected',
                'message': 'Server running but Redis unavailable'
            }), 200  # Return 200 to stay in rotation but indicate degraded state
    
    return health_bp

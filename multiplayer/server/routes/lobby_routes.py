from flask import Blueprint, jsonify, request, current_app, g
from server.utils.auth_middleware import socket_authenticated # We might need HTTP auth middleware too

# Simple HTTP auth middleware for routes
from functools import wraps
def http_authenticated(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Unauthorized'}), 401
        
        token_service = current_app.extensions['token_service']
        try:
            claims = token_service.decode(token)
            email = claims.get('email')
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
            
        user_repository = current_app.extensions['user_repository']
        user = user_repository.get_user_by_email(email)
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        g.user = user
        return f(*args, **kwargs)
    return wrapped

def init_lobby_routes(lobby_controller):
    lobby_bp = Blueprint('lobby', __name__, url_prefix='/api/multiplayer')
    
    @lobby_bp.route('/lobbies', methods=['GET'])
    def get_active_lobbies():
        """Get list of active lobbies (for debugging/admin)"""
        try:
            lobbies = lobby_controller.get_active_lobbies()
            return jsonify({'lobbies': lobbies}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @lobby_bp.route('/lobby/<lobby_code>', methods=['GET'])
    def get_lobby_details(lobby_code):
        """Get lobby details by code (for join UI)"""
        try:
            lobby_code = lobby_code.upper()
            lobby = lobby_controller.get_lobby_by_code(lobby_code)
            
            if not lobby:
                return jsonify({'error': 'Lobby not found'}), 404
            
            return jsonify({'lobby': lobby}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @lobby_bp.route('/history', methods=['GET'])
    @http_authenticated
    def get_multiplayer_history():
        """Get user's multiplayer game history (requires auth)"""
        try:
            user = g.user
            limit = request.args.get('limit', 20, type=int)
            
            # Placeholder for history
            history = []
            
            return jsonify({'history': history}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return lobby_bp

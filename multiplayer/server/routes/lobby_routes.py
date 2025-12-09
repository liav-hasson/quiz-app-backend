from flask import Blueprint, jsonify, request, current_app, g
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

    @lobby_bp.route('/lobby', methods=['POST'])
    @http_authenticated
    def create_lobby():
        """Create a new lobby"""
        try:
            user = g.user
            data = request.get_json() or {}
            
            # Extract settings with defaults
            categories = data.get('categories', ['General']) # Default category
            difficulty = data.get('difficulty', 2) # Medium
            question_timer = data.get('question_timer', 30)
            max_players = data.get('max_players', 8)
            
            result = lobby_controller.create_lobby(
                user, categories, difficulty, question_timer, max_players
            )
            
            # Transform response for frontend compatibility
            response = {
                'code': result.get('lobby_code'),
                'lobbyId': result.get('_id'),
                'lobby': result
            }
            
            return jsonify(response), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @lobby_bp.route('/join', methods=['POST'])
    @http_authenticated
    def join_lobby():
        """Join an existing lobby"""
        try:
            user = g.user
            data = request.get_json() or {}
            code = data.get('code')
            
            if not code:
                return jsonify({'error': 'Lobby code is required'}), 400
                
            result = lobby_controller.join_lobby(user, code)
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
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

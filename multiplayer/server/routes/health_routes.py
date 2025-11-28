from flask import Blueprint, jsonify

def init_health_routes():
    health_bp = Blueprint('health', __name__)
    
    @health_bp.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'quiz-multiplayer'
        }), 200
    
    return health_bp

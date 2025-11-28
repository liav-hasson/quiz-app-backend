from datetime import datetime
from flask import current_app
from flask_socketio import emit
from server.utils.auth_middleware import socket_authenticated

def register_handlers(socketio):
    
    @socketio.on('send_message')
    @socket_authenticated
    def handle_send_message(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123",
            "message": "Hello everyone!"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            message = data.get('message', '').strip()
            
            if not lobby_code or not message:
                return
            
            # Broadcast message to room
            emit('new_message', {
                'user_id': str(user['_id']),
                'username': user['username'],
                'message': message,
                'timestamp': datetime.now().isoformat()
            }, room=lobby_code)
            
        except Exception as e:
            emit('error', {'message': f'Failed to send message: {str(e)}'})

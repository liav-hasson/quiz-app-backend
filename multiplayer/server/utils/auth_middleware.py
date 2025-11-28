from functools import wraps
from flask import request, current_app
from flask_socketio import disconnect

def socket_authenticated(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # Extract token from handshake auth
        token = request.args.get('token') or \
                request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            disconnect()
            return False
        
        # Decode JWT
        token_service = current_app.extensions['token_service']
        try:
            claims = token_service.decode(token)
            email = claims.get('email')
        except Exception:
            disconnect()
            return False
        
        # Load user
        user_repository = current_app.extensions['user_repository']
        user = user_repository.get_user_by_email(email)
        
        if not user:
            disconnect()
            return False
        
        # Store user in request context for disconnect handler
        request.user = user
        
        # Pass user to handler
        return f(user, *args, **kwargs)
    
    return wrapped

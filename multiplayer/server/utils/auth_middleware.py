"""Authentication middleware for Socket.IO handlers.

This middleware validates JWT tokens and extracts user info from claims.
No database access required - all user info comes from the JWT.
"""

import logging
from functools import wraps
from flask import request, current_app
from flask_socketio import disconnect, emit

logger = logging.getLogger(__name__)


def socket_authenticated(f):
    """Decorator to require authentication for Socket.IO handlers.
    
    Extracts user info from JWT claims. No database lookup required.
    The user dict passed to handlers contains info from the JWT.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        # Extract token from handshake auth or query params
        token = request.args.get('token') or \
                request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            logger.warning("socket_auth_failed reason=no_token sid=%s", request.sid)
            emit('error', {'message': 'Authentication required', 'code': 'NO_TOKEN'})
            disconnect()
            return False
        
        # Decode JWT
        token_service = current_app.extensions.get('token_service')
        if not token_service:
            logger.error("socket_auth_failed reason=no_token_service")
            emit('error', {'message': 'Authentication service unavailable'})
            disconnect()
            return False
            
        try:
            claims = token_service.decode(token)
        except Exception as e:
            logger.warning("socket_auth_failed reason=invalid_token error=%s sid=%s", e, request.sid)
            emit('error', {'message': 'Invalid or expired token', 'code': 'INVALID_TOKEN'})
            disconnect()
            return False
        
        # Extract user info from JWT claims
        email = claims.get('email')
        if not email:
            logger.warning("socket_auth_failed reason=no_email_claim sid=%s", request.sid)
            emit('error', {'message': 'Invalid token: missing email', 'code': 'NO_EMAIL'})
            disconnect()
            return False
        
        # Build user dict from JWT claims
        # This avoids MongoDB lookup - all info comes from the token
        user = {
            '_id': claims.get('sub') or claims.get('user_id') or email,
            'email': email,
            'username': claims.get('name') or claims.get('username') or email.split('@')[0],
            'profile_picture': claims.get('picture', ''),
        }
        
        # Store user in request context for disconnect handler
        request.user = user
        
        logger.debug("socket_authenticated user=%s sid=%s", user['username'], request.sid)
        
        # Pass user to handler
        return f(user, *args, **kwargs)
    
    return wrapped

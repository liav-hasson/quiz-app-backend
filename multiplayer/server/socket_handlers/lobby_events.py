from flask import current_app, request
from flask_socketio import emit, join_room, leave_room, rooms
from server.utils.auth_middleware import socket_authenticated

def register_handlers(socketio):
    
    @socketio.on('create_lobby')
    @socket_authenticated
    def handle_create_lobby(user, data):
        """
        Expected data: {
            "categories": ["Science", "History"],
            "difficulty": 2,
            "question_timer": 30,
            "max_players": 8
        }
        """
        try:
            lobby_controller = current_app.extensions['lobby_controller']
            
            # Validate input
            categories = data.get('categories', [])
            difficulty = data.get('difficulty', 2)
            question_timer = data.get('question_timer', 30)
            max_players = data.get('max_players', 10)
            
            # Create lobby
            lobby = lobby_controller.create_lobby(
                user, categories, difficulty, question_timer, max_players
            )
            
            # Join socket room
            join_room(lobby['lobby_code'])
            
            # Emit success
            emit('lobby_created', {
                'lobby_code': lobby['lobby_code'],
                'lobby': lobby
            })
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to create lobby: {str(e)}'})

    @socketio.on('join_lobby')
    @socket_authenticated
    def handle_join_lobby(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_controller = current_app.extensions['lobby_controller']
            lobby_code = data.get('lobby_code', '').upper()
            
            # Join lobby
            lobby = lobby_controller.join_lobby(user, lobby_code)
            
            # Join socket room
            join_room(lobby_code)
            
            # Emit to player
            emit('lobby_joined', {'lobby': lobby})
            
            # Broadcast to room
            emit('player_joined', {
                'player': {
                    'user_id': str(user['_id']),
                    'username': user['username'],
                    'picture': user.get('profile_picture', ''),
                    'ready': False
                }
            }, room=lobby_code, include_self=False)
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to join lobby: {str(e)}'})

    @socketio.on('toggle_ready')
    @socket_authenticated
    def handle_toggle_ready(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123",
            "ready": true
        }
        """
        try:
            lobby_controller = current_app.extensions['lobby_controller']
            lobby_code = data.get('lobby_code', '').upper()
            ready = data.get('ready', False)
            
            # Update ready status
            lobby = lobby_controller.toggle_ready(user, lobby_code, ready)
            
            # Broadcast to room
            emit('lobby_updated', {'lobby': lobby}, room=lobby_code)
            
            # Check if all ready
            if lobby_controller.check_all_ready(lobby_code):
                emit('all_players_ready', {}, room=lobby_code)
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to update ready status: {str(e)}'})

    @socketio.on('leave_lobby')
    @socket_authenticated
    def handle_leave_lobby(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_controller = current_app.extensions['lobby_controller']
            lobby_code = data.get('lobby_code', '').upper()
            
            # Leave lobby (handles creator reassignment)
            result = lobby_controller.leave_lobby(user, lobby_code)
            
            # Leave socket room
            leave_room(lobby_code)
            
            if result.get('deleted'):
                # Lobby was deleted
                emit('lobby_closed', {}, room=lobby_code)
            else:
                # Broadcast player left
                emit('player_left', {
                    'user_id': str(user['_id']),
                    'new_creator_id': result.get('new_creator_id')
                }, room=lobby_code)
            
            emit('left_lobby', {})
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to leave lobby: {str(e)}'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """
        Auto-remove player from lobby on disconnect
        """
        try:
            # Get user from session (stored during authentication)
            user = getattr(request, 'user', None)
            if not user:
                return
            
            # Find lobby player is in (check rooms)
            player_rooms = rooms()
            lobby_controller = current_app.extensions['lobby_controller']
            
            for room in player_rooms:
                if len(room) == 6:  # Lobby code length
                    lobby_controller.mark_player_disconnected(user, room)
                    emit('player_disconnected', {
                        'user_id': str(user['_id'])
                    }, room=room)
            
        except Exception as e:
            # Silent fail on disconnect
            pass

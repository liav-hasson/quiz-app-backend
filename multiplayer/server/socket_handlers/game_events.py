import time
from flask import current_app
from flask_socketio import emit
from server.utils.auth_middleware import socket_authenticated

def register_handlers(socketio):
    
    @socketio.on('start_game')
    @socket_authenticated
    def handle_start_game(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123"
        }
        Only lobby creator can start when all ready
        """
        try:
            lobby_controller = current_app.extensions['lobby_controller']
            lobby_code = data.get('lobby_code', '').upper()
            
            # Validate can start
            lobby = lobby_controller.validate_game_start(lobby_code, str(user['_id']))
            
            # Start countdown
            emit('countdown_started', {
                'countdown_duration': current_app.config['GAME_COUNTDOWN_DURATION']
            }, room=lobby_code)
            
            # Schedule game start after countdown
            socketio.start_background_task(
                start_game_after_countdown,
                socketio,
                current_app._get_current_object(), # Pass app instance
                lobby_code,
                current_app.config['GAME_COUNTDOWN_DURATION']
            )
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to start game: {str(e)}'})

    @socketio.on('submit_answer')
    @socket_authenticated
    def handle_submit_answer(user, data):
        """
        Expected data: {
            "lobby_code": "ABC123",
            "answer": "Option A",
            "time_taken": 5.3  # seconds
        }
        """
        try:
            game_controller = current_app.extensions['game_controller']
            lobby_code = data.get('lobby_code', '').upper()
            answer = data.get('answer')
            time_taken = data.get('time_taken', 0)
            
            # Submit answer (validates, calculates score, records)
            result = game_controller.submit_answer(
                lobby_code,
                str(user['_id']),
                answer,
                time_taken
            )
            
            # Emit only to submitting player
            emit('answer_recorded', {
                'points_earned': result['points_earned'],
                'is_correct': result['is_correct'],
                'time_taken': time_taken
            })
            
            # Optionally emit to room that player answered (without revealing answer)
            emit('player_answered', {
                'user_id': str(user['_id']),
                'username': user['username']
            }, room=lobby_code, include_self=False)
            
        except ValueError as e:
            emit('error', {'message': str(e)})
        except Exception as e:
            emit('error', {'message': f'Failed to submit answer: {str(e)}'})

def start_game_after_countdown(socketio, app, lobby_code, countdown_seconds):
    """Background task to start game after countdown"""
    time.sleep(countdown_seconds)
    
    with app.app_context():
        try:
            game_controller = app.extensions['game_controller']
            
            # Initialize game (fetch questions, create session)
            game_session = game_controller.start_game(lobby_code)
            
            # Emit first question
            emit_next_question(socketio, app, lobby_code)
            
        except Exception as e:
            socketio.emit('error', {
                'message': f'Failed to start game: {str(e)}'
            }, room=lobby_code, namespace='/')

def emit_next_question(socketio, app, lobby_code):
    """Emit current question to lobby and start timer"""
    with app.app_context():
        try:
            game_controller = app.extensions['game_controller']
            lobby_repository = app.extensions['lobby_repository']
            
            # Get current question (without correct answer)
            question_data = game_controller.get_current_question(lobby_code)
            lobby = lobby_repository.get_lobby_by_code(lobby_code)
            
            if not question_data:
                # Game complete
                finalize_game(socketio, app, lobby_code)
                return
            
            # Emit question to room
            socketio.emit('question_started', {
                'question': question_data,
                'question_index': question_data['index'],
                'total_questions': question_data['total'],
                'timer_duration': lobby['question_timer']
            }, room=lobby_code, namespace='/')
            
            # Schedule auto-advance when timer expires
            socketio.start_background_task(
                auto_advance_question,
                socketio,
                app,
                lobby_code,
                lobby['question_timer']
            )
            
        except Exception as e:
            socketio.emit('error', {
                'message': f'Failed to emit question: {str(e)}'
            }, room=lobby_code, namespace='/')

def auto_advance_question(socketio, app, lobby_code, timer_duration):
    """Auto-advance to next question when timer expires"""
    time.sleep(timer_duration)
    
    with app.app_context():
        try:
            game_controller = app.extensions['game_controller']
            lobby_repository = app.extensions['lobby_repository']
            
            # Record auto-fail for players who didn't answer
            session = game_controller.game_session_repository.get_game_session_by_lobby(lobby_code)
            lobby = lobby_repository.get_lobby_by_code(lobby_code)
            current_index = session['current_question_index']
            
            for player in lobby['players']:
                user_id = player['user_id']
                
                # Check if player answered this question
                player_answers = session['player_answers'].get(user_id, [])
                answered_indices = [a['question_index'] for a in player_answers]
                
                if current_index not in answered_indices:
                    # Auto-record wrong answer with 0 points
                    game_controller.record_auto_fail(lobby_code, user_id, current_index)

            # Get correct answer and current scores
            question_results = game_controller.get_question_results(lobby_code)
            
            # Emit question ended with results
            socketio.emit('question_ended', {
                'correct_answer': question_results['correct_answer'],
                'player_scores': question_results['player_scores'],
                'player_answers': question_results['player_answers']
            }, room=lobby_code, namespace='/')
            
            # Wait interval before next question
            time.sleep(app.config['QUESTION_INTERVAL_DURATION'])
            
            # Advance to next question
            has_next = game_controller.advance_to_next_question(lobby_code)
            
            if has_next:
                emit_next_question(socketio, app, lobby_code)
            else:
                finalize_game(socketio, app, lobby_code)
            
        except Exception as e:
            socketio.emit('error', {
                'message': f'Failed to advance question: {str(e)}'
            }, room=lobby_code, namespace='/')

def finalize_game(socketio, app, lobby_code):
    """Finalize game, award XP, emit results"""
    with app.app_context():
        try:
            game_controller = app.extensions['game_controller']
            
            # Calculate final scores and award XP
            results = game_controller.finalize_game(lobby_code)
            
            # Emit game ended
            socketio.emit('game_ended', {
                'final_rankings': results['rankings'],
                'xp_awarded': results['xp_awarded']
            }, room=lobby_code, namespace='/')
            
            # Schedule lobby cleanup (optional)
            # socketio.start_background_task(cleanup_lobby, lobby_code, 300)
            
        except Exception as e:
            socketio.emit('error', {
                'message': f'Failed to finalize game: {str(e)}'
            }, room=lobby_code, namespace='/')

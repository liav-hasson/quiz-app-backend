"""Socket.IO handlers for game events.

Game state is managed by the API server and stored in Redis.
These handlers receive game events via Redis pub/sub and can also
handle real-time player actions that need immediate feedback.
"""

import time
import logging
from flask import request, current_app
from flask_socketio import emit

from server.utils.auth_middleware import socket_authenticated

logger = logging.getLogger(__name__)


def register_handlers(socketio):
    """Register game-related Socket.IO event handlers."""

    @socketio.on('start_game')
    @socket_authenticated
    def handle_start_game(user, data):
        """Legacy handler - tells client to use REST API.
        
        Game start is now handled by POST /api/multiplayer/lobby/{code}/start
        """
        emit('error', {
            'message': 'Please use the REST API to start the game',
            'code': 'USE_REST_API'
        })

    @socketio.on('submit_answer')
    @socket_authenticated
    def handle_submit_answer(user, data):
        """Handle answer submission during game.
        
        This is one of the few operations that still goes through WebSocket
        for low-latency feedback. The answer is validated and scored here,
        then published to Redis for score updates.
        
        Expected data: {
            "lobby_code": "ABC123",
            "answer": "Option A",
            "time_taken": 5.3
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            answer = data.get('answer')
            time_taken = data.get('time_taken', 0)
            
            if not lobby_code or answer is None:
                emit('error', {'message': 'lobby_code and answer required'})
                return
            
            redis_client = current_app.extensions.get('redis_client')
            if not redis_client:
                emit('error', {'message': 'Game service unavailable'})
                return
            
            # Get game state from Redis
            game_state = redis_client.get_game_state(lobby_code)
            if not game_state:
                emit('error', {'message': 'Game not found or not started'})
                return
            
            user_id = str(user.get('_id', ''))
            current_question = game_state['current_question']  # No fallback - must exist
            correct_answer = current_question['correct_answer']  # No fallback - must exist
            
            # Calculate score using Kahoot-style formula (0-100 points)
            is_correct = answer == correct_answer
            question_timer = game_state['question_timer']  # No fallback - must exist
            
            if is_correct:
                # Score = 100 - (time_taken / question_timer * 100)
                # Fast answers get more points, timeout gets 0
                time_ratio = min(time_taken / question_timer, 1.0)
                points_earned = max(0, round(100 - (time_ratio * 100)))
            else:
                points_earned = 0
            
            # Update player score in Redis
            player_scores = game_state.get('player_scores', {})
            old_score = player_scores.get(user_id, 0)
            player_scores[user_id] = old_score + points_earned
            game_state['player_scores'] = player_scores
            
            logger.info("score_accumulation user=%s old=%d earned=%d new=%d", 
                       user.get('username'), old_score, points_earned, player_scores[user_id])
            
            # Record answer
            player_answers = game_state.get('player_answers', {})
            if user_id not in player_answers:
                player_answers[user_id] = []
            player_answers[user_id].append({
                'question_index': game_state.get('current_question_index', 0),
                'answer': answer,
                'is_correct': is_correct,
                'points': points_earned,
                'time_taken': time_taken
            })
            game_state['player_answers'] = player_answers
            
            # DEBUG: Log answer tracking for auto-advance
            logger.info("answer_tracking lobby=%s user=%s question_index=%d total_answers=%d", 
                       lobby_code, user_id, game_state.get('current_question_index', 0), 
                       len(player_answers))
            
            # Save updated state
            redis_client.set_game_state(lobby_code, game_state)
            
            # CRITICAL: Update score in MongoDB via API
            import requests
            import os
            from common.utils.config import settings
            
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if internal_secret:
                try:
                    api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/lobby/{lobby_code}/update-score"
                    requests.post(api_url, json={
                        "user_id": user_id,
                        "score": player_scores[user_id]
                    }, headers={
                        "X-Internal-Secret": internal_secret
                    }, timeout=5)
                    logger.info("score_persisted_to_db user=%s lobby=%s score=%d", user.get('username'), lobby_code, player_scores[user_id])
                except Exception as db_error:
                    logger.error("failed_to_persist_score user=%s lobby=%s error=%s", user.get('username'), lobby_code, str(db_error))
            
            # Emit result to submitting player only
            emit('answer_recorded', {
                'points_earned': points_earned,
                'is_correct': is_correct,
                'time_taken': time_taken,
                'new_total': player_scores[user_id],
                'correct_answer': correct_answer
            })
            
            # Notify room that player answered (without revealing answer)
            emit('player_answered', {
                'user_id': user_id,
                'username': user.get('username', '')
            }, room=lobby_code, include_self=False)
            
            logger.info("answer_submitted user=%s lobby=%s correct=%s points=%d",
                       user.get('username'), lobby_code, is_correct, points_earned)
            
        except Exception as e:
            logger.error("submit_answer_failed error=%s", e)
            emit('error', {'message': f'Failed to submit answer: {str(e)}'})

    @socketio.on('request_scores')
    @socket_authenticated
    def handle_request_scores(user, data):
        """Request current game scores.
        
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            
            redis_client = current_app.extensions.get('redis_client')
            if not redis_client:
                emit('error', {'message': 'Service unavailable'})
                return
            
            game_state = redis_client.get_game_state(lobby_code)
            if not game_state:
                emit('error', {'message': 'Game not found'})
                return
            
            emit('scores_updated', {
                'player_scores': game_state.get('player_scores', {}),
                'current_question_index': game_state.get('current_question_index', 0),
                'total_questions': game_state.get('total_questions', 0)
            })
            
        except Exception as e:
            logger.error("request_scores_failed error=%s", e)
            emit('error', {'message': f'Failed to get scores: {str(e)}'})

    @socketio.on('rejoin_game')
    @socket_authenticated
    def handle_rejoin_game(user, data):
        """Handle a player trying to rejoin an active game.
        
        Validates the user is a member of the lobby, then returns the
        current game state from Redis so the client can hydrate and resume.
        
        Expected data: {
            "lobby_code": "ABC123"
        }
        """
        try:
            lobby_code = data.get('lobby_code', '').upper()
            
            if not lobby_code:
                emit('rejoin_game_response', {'status': 'error', 'message': 'Lobby code required'})
                return
            
            redis_client = current_app.extensions.get('redis_client')
            if not redis_client:
                emit('rejoin_game_response', {'status': 'error', 'message': 'Service unavailable'})
                return
            
            user_id = str(user.get('_id', ''))
            
            # Validate user is a member of this lobby via API
            import requests
            import os
            from common.utils.config import settings
            
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if not internal_secret:
                emit('rejoin_game_response', {'status': 'error', 'message': 'Service misconfigured'})
                return
            
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/lobby/{lobby_code}"
            lobby_response = requests.get(api_url, headers={
                "X-Internal-Secret": internal_secret
            }, timeout=5)
            
            if lobby_response.status_code != 200:
                emit('rejoin_game_response', {'status': 'ended', 'message': 'Lobby not found'})
                return
            
            lobby = lobby_response.json().get('lobby')
            if not lobby:
                emit('rejoin_game_response', {'status': 'ended', 'message': 'Lobby not found'})
                return
            
            # Check that user is actually a member of this lobby
            player_ids = [p['user_id'] for p in lobby.get('players', [])]
            if user_id not in player_ids:
                logger.warning("rejoin_denied_not_member user=%s lobby=%s", user.get('username'), lobby_code)
                emit('rejoin_game_response', {'status': 'error', 'message': 'You are not a member of this lobby'})
                return
            
            # Check lobby status
            lobby_status = lobby.get('status', '')
            if lobby_status == 'completed':
                emit('rejoin_game_response', {'status': 'ended', 'message': 'Game has ended'})
                return
            
            if lobby_status != 'in_progress':
                emit('rejoin_game_response', {'status': 'ended', 'message': 'No active game'})
                return
            
            # Get game state from Redis
            game_state = redis_client.get_game_state(lobby_code)
            if not game_state:
                emit('rejoin_game_response', {'status': 'ended', 'message': 'Game state not found'})
                return
            
            # Join the socket room so they receive future events
            from flask_socketio import join_room
            join_room(lobby_code)
            
            # Calculate time remaining for current question
            question_timer = game_state.get('question_timer', 30)
            question_start_time = game_state.get('question_start_time')
            if question_start_time:
                elapsed = time.time() - question_start_time
                time_remaining = max(0, round(question_timer - elapsed))
            else:
                time_remaining = question_timer
            
            # Check if this player already answered the current question
            current_question_index = game_state.get('current_question_index', -1)
            player_answers = game_state.get('player_answers', {})
            user_answers = player_answers.get(user_id, [])
            current_answer = next(
                (a for a in user_answers if a.get('question_index') == current_question_index), None
            )
            has_answered = current_answer is not None
            
            # Get the current question
            current_question = game_state.get('current_question')
            question_data = None
            if current_question and current_question_index >= 0:
                question_data = {
                    'question': current_question.get('question_text', ''),
                    'options': current_question.get('options', []),
                    'category': current_question.get('category', 'General'),
                    'difficulty': current_question.get('difficulty', 2),
                    'question_number': current_question_index + 1,
                    'total_questions': game_state.get('total_questions', 0),
                    'time_limit': question_timer,
                }
                # Include answer details if player already answered
                if has_answered:
                    question_data['correct_answer'] = current_question.get('correct_answer', '')
            
            # Build standings
            player_scores = game_state.get('player_scores', {})
            standings = []
            for player in lobby.get('players', []):
                pid = player['user_id']
                p_answers = player_answers.get(pid, [])
                correct_count = sum(1 for a in p_answers if a.get('is_correct', False))
                standings.append({
                    'user_id': pid,
                    'username': player['username'],
                    'score': player_scores.get(pid, 0),
                    'correct_answers': correct_count,
                })
            standings.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info("rejoin_game_success user=%s lobby=%s question=%d/%d time_remaining=%d has_answered=%s",
                        user.get('username'), lobby_code, current_question_index + 1,
                        game_state.get('total_questions', 0), time_remaining, has_answered)
            
            response_data = {
                'status': 'active',
                'question': question_data,
                'time_remaining': time_remaining,
                'has_answered': has_answered,
                'standings': standings,
                'total_questions': game_state.get('total_questions', 0),
            }
            # Include answer details so frontend can show feedback
            if has_answered and current_answer:
                response_data['answer_details'] = {
                    'answer': current_answer.get('answer', ''),
                    'is_correct': current_answer.get('is_correct', False),
                    'points': current_answer.get('points', 0),
                }
            emit('rejoin_game_response', response_data)
            
        except Exception as e:
            logger.error("rejoin_game_failed user=%s error=%s", user.get('username', '?'), str(e), exc_info=True)
            emit('rejoin_game_response', {'status': 'error', 'message': f'Rejoin failed: {str(e)}'})

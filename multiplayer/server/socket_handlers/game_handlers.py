"""Socket.IO handlers for game events.

Game state is managed by the API server and stored in Redis.
These handlers receive game events via Redis pub/sub and can also
handle real-time player actions that need immediate feedback.
"""

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

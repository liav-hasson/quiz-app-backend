import time
import logging
from flask import current_app
from flask_socketio import emit
from common.redis_client import get_redis_client, EventType

logger = logging.getLogger(__name__)

# NOTE: Socket handlers for game events are in game_handlers.py
# This file only contains the start_game_with_countdown function
# which is called from the Redis event listener.

def start_game_with_countdown(socketio, app, lobby_code, countdown_seconds=3, question_list=None, question_timer=10):
    """Background task to handle countdown and start game.
    
    This is called from the Redis event listener when GAME_STARTING event is received.
    
    Args:
        socketio: SocketIO instance
        app: Flask app instance
        lobby_code: Lobby code
        countdown_seconds: Countdown duration (default 3)
        question_list: List of question set configurations from lobby
        question_timer: Time limit for each question in seconds
    """
    with app.app_context():
        try:
            redis_client = get_redis_client()
            
            # Emit countdown_started event
            socketio.emit('countdown_started', {
                'seconds': countdown_seconds,
                'lobby_code': lobby_code
            }, room=lobby_code, namespace='/')
            
            logger.info("game_countdown_started lobby=%s seconds=%d", lobby_code, countdown_seconds)
            
            # Wait for countdown
            time.sleep(countdown_seconds)
            
            # Call API to create game session and generate questions
            import requests
            import os
            from common.utils.config import settings
            
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if not internal_secret:
                raise Exception("INTERNAL_SERVICE_SECRET not configured")
            
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/game-session/create"
            response = requests.post(api_url, json={
                "lobby_code": lobby_code,
                "question_list": question_list or []
            }, headers={
                "X-Internal-Secret": internal_secret
            }, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"API call failed: {response.text}")
            
            game_data = response.json()
            session_id = game_data["session_id"]
            questions = game_data["questions"]
            
            # Get lobby data to initialize player scores
            lobby_state = redis_client.get_lobby_state(lobby_code) or {}
            players = lobby_state.get('players', [])
            
            # Initialize player scores to 0 for all players
            player_scores = {str(player.get('user_id', player.get('_id', ''))): 0 for player in players}
            
            # Store game session in Redis for fast access
            redis_client.set_game_state(lobby_code, {
                "session_id": session_id,
                "lobby_code": lobby_code,
                "current_question_index": -1,
                "total_questions": len(questions),
                "questions": questions,
                "status": "in_progress",
                "question_timer": question_timer,
                "player_scores": player_scores,  # Initialize scores
                "player_answers_tracking": {}  # Track which questions each player answered
            }, ttl_seconds=3600)
            
            # Emit GAME_STARTED directly to clients (don't publish to Redis to avoid duplicate relay)
            socketio.emit('game_started', {
                "session_id": session_id,
                "total_questions": len(questions),
                "lobby_code": lobby_code
            }, room=lobby_code, namespace='/')
            
            logger.info("game_started lobby=%s session=%s questions=%d", 
                       lobby_code, session_id, len(questions))
            
            # Emit initial scores (all players at 0) so leaderboard shows immediately
            initial_standings = [
                {
                    'user_id': str(player.get('user_id', player.get('_id', ''))),
                    'username': player.get('username', 'Unknown'),
                    'score': 0
                }
                for player in players
            ]
            socketio.emit('scores_updated', {
                'standings': initial_standings
            }, room=lobby_code, namespace='/')
            
            # Start main game loop in a single background task (no concurrent tasks)
            time.sleep(1)
            socketio.start_background_task(
                run_game_loop,
                socketio,
                app,
                lobby_code
            )
            
        except Exception as e:
            logger.error("start_game_with_countdown_failed lobby=%s error=%s", lobby_code, str(e), exc_info=True)
            socketio.emit('error', {
                'message': f'Failed to start game: {str(e)}'
            }, room=lobby_code, namespace='/')

def run_game_loop(socketio, app, lobby_code):
    """Main game loop - runs sequentially through all questions.
    
    This runs as a single background task to avoid race conditions from
    multiple concurrent tasks emitting events out of order.
    """
    with app.app_context():
        try:
            redis_client = get_redis_client()
            
            # Get game state from Redis
            game_state = redis_client.get_game_state(lobby_code)
            if not game_state:
                logger.error("game_state_missing lobby=%s", lobby_code)
                socketio.emit('error', {'message': 'Game state not found'}, room=lobby_code, namespace='/')
                return
            
            questions = game_state.get('questions', [])
            question_timer = game_state['question_timer']
            
            # Loop through all questions sequentially
            for question_index in range(len(questions)):
                try:
                    # Emit question
                    question = questions[question_index]
                    
                    # CRITICAL: Re-fetch game state to get latest player_scores
                    # (scores are updated by submit_answer handler during question)
                    game_state = redis_client.get_game_state(lobby_code)
                    if not game_state:
                        logger.error("game_state_lost_mid_game lobby=%s question=%d", lobby_code, question_index)
                        raise RuntimeError("Game state lost during game")
                    
                    # Log current scores for debugging
                    current_scores = game_state.get('player_scores', {})
                    logger.info("question_start_scores lobby=%s question=%d scores=%s", 
                               lobby_code, question_index + 1, current_scores)
                    
                    # Update current question index in Redis
                    game_state['current_question_index'] = question_index
                    game_state['current_question'] = question
                    redis_client.set_game_state(lobby_code, game_state, ttl_seconds=3600)
                    
                    # Emit QUESTION_SENT directly (don't publish to Redis to avoid duplicate relay)
                    socketio.emit('question_started', {
                        "question": question['question_text'],
                        "options": question['options'],
                        "category": question.get('category', 'General'),
                        "difficulty": question.get('difficulty', 2),
                        "question_number": question_index + 1,
                        "total_questions": len(questions),
                        "time_limit": question_timer
                    }, room=lobby_code, namespace='/')
                    
                    logger.info("question_emitted lobby=%s question=%d/%d", 
                               lobby_code, question_index + 1, len(questions))
                    
                    # Wait for timer to expire OR all players to answer
                    # Check every 0.5 seconds if all players have answered
                    elapsed = 0
                    check_interval = 0.5
                    
                    # Get player count from lobby
                    lobby_state = redis_client.get_lobby_state(lobby_code) or {}
                    player_count = len(lobby_state.get('players', []))
                    
                    while elapsed < question_timer:
                        time.sleep(check_interval)
                        elapsed += check_interval
                        
                        # Check if all players have answered
                        current_state = redis_client.get_game_state(lobby_code)
                        if current_state:
                            player_answers = current_state.get('player_answers', {})
                            # Count players who answered THIS question
                            answered_count = sum(
                                1 for user_answers in player_answers.values()
                                if any(a.get('question_index') == question_index for a in user_answers)
                            )
                            
                            if answered_count >= player_count and player_count > 0:
                                logger.info("all_players_answered lobby=%s question=%d elapsed=%.1f", 
                                           lobby_code, question_index + 1, elapsed)
                                break
                    
                    # End question and show results
                    end_current_question(socketio, app, lobby_code, question_index)
                    
                    # Wait 3 seconds to show results before next question
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error("question_loop_error lobby=%s question=%d error=%s", 
                               lobby_code, question_index + 1, str(e), exc_info=True)
                    # Continue to next question even if one fails
            
            # All questions complete - finalize game
            logger.info("game_questions_complete lobby=%s", lobby_code)
            finalize_game(socketio, app, lobby_code)
            
        except Exception as e:
            logger.error("game_loop_failed lobby=%s error=%s", lobby_code, str(e), exc_info=True)
            socketio.emit('error', {
                'message': f'Game loop failed: {str(e)}'
            }, room=lobby_code, namespace='/')

def end_current_question(socketio, app, lobby_code, question_index):
    """End the current question - record auto-fails and emit results.
    
    Called from the main game loop after timer expires.
    """
    with app.app_context():
        try:
            import requests
            import os
            from common.utils.config import settings
            
            redis_client = get_redis_client()
            
            # Get game state
            game_state = redis_client.get_game_state(lobby_code)
            if not game_state:
                logger.error("game_state_missing_end_question lobby=%s", lobby_code)
                return
            
            questions = game_state.get('questions', [])
            player_answers_tracking = game_state.get('player_answers_tracking', {})
            
            # Get lobby data
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if not internal_secret:
                logger.error("INTERNAL_SERVICE_SECRET not configured")
                return
            
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/lobby/{lobby_code}"
            lobby_response = requests.get(api_url, headers={
                "X-Internal-Secret": internal_secret
            }, timeout=5)
            
            if lobby_response.status_code != 200:
                logger.error("failed_to_get_lobby lobby=%s", lobby_code)
                return
            
            lobby = lobby_response.json().get('lobby')
            if not lobby:
                logger.error("lobby_missing lobby=%s", lobby_code)
                return
            
            # Record auto-fail for players who didn't answer
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/game-action/record-auto-fail"
            
            for player in lobby.get('players', []):
                user_id = player['user_id']
                player_answered_indices = player_answers_tracking.get(user_id, [])
                
                if question_index not in player_answered_indices:
                    try:
                        requests.post(api_url, json={
                            "lobby_code": lobby_code,
                            "user_id": user_id,
                            "question_index": question_index
                        }, headers={
                            "X-Internal-Secret": internal_secret
                        }, timeout=5)
                        logger.debug("auto_fail_recorded lobby=%s user=%s question=%d", 
                                   lobby_code, user_id, question_index)
                    except Exception as e:
                        logger.warning("auto_fail_request_failed user=%s error=%s", user_id, str(e))
            
            # Get updated scores and correct answer
            correct_answer = questions[question_index].get('correct_answer', '')
            
            # Build standings with username for leaderboard display
            # Use scores from Redis game state (more up-to-date than MongoDB)
            # Refresh game state to get latest player_scores after answer submissions
            game_state = redis_client.get_game_state(lobby_code) or game_state
            player_scores = game_state.get('player_scores', {})
            player_answers = game_state.get('player_answers', {})
            
            standings = []
            for player in lobby.get('players', []):
                user_id = player['user_id']
                # Count correct answers for this player
                user_answers = player_answers.get(user_id, [])
                correct_count = sum(1 for a in user_answers if a.get('is_correct', False))
                
                standings.append({
                    "user_id": user_id,
                    "username": player['username'],
                    "score": player_scores.get(user_id, 0),
                    "correct_answers": correct_count
                })
            
            # Sort by score descending
            standings.sort(key=lambda x: x['score'], reverse=True)
            
            # Emit ROUND_ENDED directly (don't publish to Redis to avoid duplicate relay)
            socketio.emit('question_ended', {
                "correct_answer": correct_answer,
                "standings": standings
            }, room=lobby_code, namespace='/')
            
            # Emit SCORES_UPDATED directly (don't publish to Redis to avoid duplicate relay)
            socketio.emit('scores_updated', {
                "standings": standings
            }, room=lobby_code, namespace='/')
            
            logger.info("question_ended lobby=%s correct_answer=%s", 
                       lobby_code, correct_answer)
            
        except Exception as e:
            logger.error("end_question_failed lobby=%s question=%d error=%s", 
                        lobby_code, question_index, str(e), exc_info=True)



def finalize_game(socketio, app, lobby_code):
    """Finalize game, calculate final scores, award XP, and emit results."""
    with app.app_context():
        try:
            import requests
            import os
            from common.utils.config import settings
            
            redis_client = get_redis_client()
            
            # Get final player scores from lobby via API (updated real-time during game)
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if not internal_secret:
                logger.error("INTERNAL_SERVICE_SECRET not configured")
                return
            
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/lobby/{lobby_code}"
            lobby_response = requests.get(api_url, headers={
                "X-Internal-Secret": internal_secret
            }, timeout=5)
            
            if lobby_response.status_code != 200:
                logger.error("failed_to_get_lobby_finalize lobby=%s", lobby_code)
                return
            
            lobby = lobby_response.json().get('lobby')
            
            if not lobby:
                logger.error("lobby_not_found_finalize lobby=%s", lobby_code)
                return
            
            # Get final scores from Redis (most up-to-date), not MongoDB
            game_state = redis_client.get_game_state(lobby_code)
            player_scores = game_state.get('player_scores', {}) if game_state else {}
            player_answers = game_state.get('player_answers', {}) if game_state else {}
            
            # Fallback to MongoDB if Redis has no scores
            if not player_scores:
                player_scores = {p['user_id']: p.get('score', 0) for p in lobby.get('players', [])}
            
            # Build correct_answers map
            correct_answers_map = {}
            for user_id, answers in player_answers.items():
                correct_answers_map[user_id] = sum(1 for a in answers if a.get('is_correct', False))
            
            # Call API to finalize game and award XP
            internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
            if not internal_secret:
                logger.error("INTERNAL_SERVICE_SECRET not configured")
                return
            
            api_url = f"http://{settings.api_host}:{settings.api_port}/api/multiplayer/game-action/finalize"
            response = requests.post(api_url, json={
                "lobby_code": lobby_code,
                "player_scores": player_scores,
                "correct_answers": correct_answers_map
            }, headers={
                "X-Internal-Secret": internal_secret
            }, timeout=10)
            
            if response.status_code != 200:
                logger.error("finalize_api_failed lobby=%s status=%d", lobby_code, response.status_code)
                return
            
            results = response.json()
            
            logger.info("game_finalized lobby=%s winner=%s", 
                       lobby_code, results['rankings'][0]['username'] if results.get('rankings') else 'none')
            
            # Emit GAME_ENDED directly (don't publish to Redis to avoid duplicate relay)
            socketio.emit('game_ended', {
                "final_standings": results.get('rankings', []),
                "xp_awarded": results.get('xp_awarded', {})
            }, room=lobby_code, namespace='/')
            
            logger.info("game_ended_event_published lobby=%s", lobby_code)
            
        except Exception as e:
            logger.error("finalize_game_failed lobby=%s error=%s", 
                        lobby_code, str(e), exc_info=True)
            socketio.emit('error', {
                'message': f'Failed to finalize game: {str(e)}'
            }, room=lobby_code, namespace='/')

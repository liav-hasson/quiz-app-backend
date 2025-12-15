"""Multiplayer routes for the Quiz API.

This module handles REST API endpoints for multiplayer lobby management.
All lobby mutations publish events to Redis for the WebSocket server to relay.

Architecture:
    Frontend → API Server (this) → MongoDB + Redis Pub → WebSocket Server → Clients
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Optional

from flask import Blueprint, current_app, g, jsonify, request

from common.redis_client import EventType, get_redis_client
from common.utils.config import settings
from controllers.quiz_controller import QuizController

logger = logging.getLogger(__name__)

multiplayer_bp = Blueprint("multiplayer", __name__, url_prefix="/api/multiplayer")

# Will be set during initialization
quiz_controller: Optional[QuizController] = None


def get_lobby_repository():
    """Get the lobby repository from app extensions."""
    return current_app.extensions.get("lobby_repository")


def get_quiz_repository():
    """Get the quiz repository from app extensions."""
    return current_app.extensions.get("quiz_repository")


def get_questions_repository():
    """Get the questions repository from app extensions."""
    return current_app.extensions.get("questions_repository")


def get_db_controller():
    """Get the database controller from app extensions."""
    return current_app.extensions.get("db_controller")


def get_user_repository():
    """Get the user repository from app extensions."""
    return current_app.extensions.get("user_repository")


def multiplayer_authenticated(f):
    """Decorator to require authentication and set g.user for multiplayer endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # g.user is set by the main auth middleware in app.py
        if not hasattr(g, "user") or not g.user:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


def serialize_lobby(lobby: dict) -> dict:
    """Serialize a lobby document for JSON response."""
    if not lobby:
        return None

    # Ensure _id is string
    if "_id" in lobby:
        lobby["_id"] = str(lobby["_id"])

    # Convert datetime objects to ISO strings
    for field in ["created_at", "updated_at", "expire_at"]:
        if field in lobby and hasattr(lobby[field], "isoformat"):
            lobby[field] = lobby[field].isoformat()

    return lobby


def publish_lobby_event(lobby_code: str, event_type: EventType, data: dict) -> None:
    """Publish a lobby event to Redis for WebSocket relay.

    This is a fire-and-forget operation - errors are logged but not raised.
    """
    try:
        redis_client = get_redis_client()
        if redis_client.ping():
            redis_client.publish_lobby_event(lobby_code, event_type, data)
            logger.debug("published_lobby_event code=%s type=%s", lobby_code, event_type.value)
        else:
            logger.warning("redis_unavailable skipping_publish code=%s type=%s", lobby_code, event_type.value)
    except Exception as e:
        # Log but don't fail the request - WebSocket updates are best-effort
        logger.error("redis_publish_failed code=%s type=%s error=%s", lobby_code, event_type.value, e)


# =============================================================================
# Public Endpoints (no auth required)
# =============================================================================

@multiplayer_bp.route("/lobbies", methods=["GET"])
def get_active_lobbies():
    """Get list of active lobbies (for browsing).

    Returns:
        JSON list of active lobbies with basic info.
    """
    try:
        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobbies = lobby_repository.get_active_lobbies()

        # Serialize and filter sensitive data
        public_lobbies = []
        for lobby in lobbies:
            public_lobbies.append({
                "lobby_code": lobby["lobby_code"],
                "creator_username": lobby["creator_username"],
                "categories": lobby["categories"],
                "difficulty": lobby["difficulty"],
                "player_count": len(lobby["players"]),
                "max_players": lobby["max_players"],
                "status": lobby["status"],
            })

        return jsonify({"lobbies": public_lobbies}), 200
    except Exception as e:
        logger.error("get_active_lobbies_failed error=%s", e)
        return jsonify({"error": "Failed to fetch lobbies"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>", methods=["GET"])
def get_lobby_details(lobby_code: str):
    """Get lobby details by code.

    Args:
        lobby_code: The 6-character lobby code.

    Returns:
        JSON with lobby details or 404 if not found.
    """
    try:
        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobby_code = lobby_code.upper()
        lobby = lobby_repository.get_lobby_by_code(lobby_code)

        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        return jsonify({"lobby": serialize_lobby(lobby)}), 200
    except Exception as e:
        logger.error("get_lobby_details_failed code=%s error=%s", lobby_code, e)
        return jsonify({"error": "Failed to fetch lobby"}), 500


# =============================================================================
# Authenticated Endpoints
# =============================================================================

@multiplayer_bp.route("/lobby", methods=["POST"])
@multiplayer_authenticated
def create_lobby():
    """Create a new multiplayer lobby.

    Request Body:
        {
            "categories": ["Science", "History"],  # Optional, default: ["General"]
            "difficulty": 2,                       # Optional, 1-3, default: 2
            "question_timer": 30,                  # Optional, seconds, default: 30
            "max_players": 8                       # Optional, 2-20, default: 8
        }

    Returns:
        JSON with lobby code and details.
    """
    try:
        user = g.user
        data = request.get_json() or {}

        lobby_repository = get_lobby_repository()
        quiz_repository = get_quiz_repository()

        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        # Extract and validate settings
        categories = data.get("categories", ["General"])
        difficulty = data.get("difficulty", 2)
        question_timer = data.get("question_timer", 30)  # Default: 30 seconds
        max_players = data.get("max_players", 8)

        # Validation
        if not categories:
            return jsonify({"error": "At least one category is required"}), 400

        if difficulty not in [1, 2, 3]:
            return jsonify({"error": "Difficulty must be 1, 2, or 3"}), 400

        if max_players < 2 or max_players > 20:
            return jsonify({"error": "Max players must be between 2 and 20"}), 400

        if question_timer < 10 or question_timer > 120:
            return jsonify({"error": "Question timer must be between 10 and 120 seconds"}), 400

        # Validate categories exist (optional - allow custom categories)
        if quiz_repository:
            valid_categories = quiz_repository.get_all_topics()
            for cat in categories:
                if valid_categories and cat not in valid_categories:
                    logger.warning("unknown_category category=%s", cat)

        # Create the lobby
        lobby = lobby_repository.create_lobby(
            user, categories, difficulty, question_timer, max_players
        )

        # Publish event to Redis
        publish_lobby_event(
            lobby["lobby_code"],
            EventType.LOBBY_CREATED,
            {"lobby": serialize_lobby(lobby.copy())}
        )

        # Response format for frontend compatibility
        response = {
            "code": lobby["lobby_code"],
            "lobbyId": lobby["_id"],
            "lobby": serialize_lobby(lobby)
        }

        logger.info("lobby_created code=%s creator=%s", lobby["lobby_code"], user["username"])
        return jsonify(response), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("create_lobby_failed error=%s", e, exc_info=True)
        return jsonify({"error": "Failed to create lobby"}), 500


@multiplayer_bp.route("/join", methods=["POST"])
@multiplayer_authenticated
def join_lobby():
    """Join an existing lobby.

    Request Body:
        {
            "code": "ABC123"  # Required, the 6-character lobby code
        }

    Returns:
        JSON with updated lobby details.
    """
    try:
        user = g.user
        data = request.get_json() or {}
        code = data.get("code", "").upper()

        if not code:
            return jsonify({"error": "Lobby code is required"}), 400

        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        # Get lobby first to check status
        lobby = lobby_repository.get_lobby_by_code(code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        if lobby["status"] != "waiting":
            # Allow rejoining if already a player
            is_player = any(p["user_id"] == str(user["_id"]) for p in lobby["players"])
            if not is_player:
                return jsonify({"error": "Game already in progress"}), 400

        # Add player to lobby
        updated_lobby = lobby_repository.add_player_to_lobby(code, user)

        # Build player data for the event
        player_data = {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "picture": user.get("profile_picture", ""),
            "ready": False
        }

        # Publish player joined event to Redis
        publish_lobby_event(
            code,
            EventType.PLAYER_JOINED,
            {
                "player": player_data,
                "lobby": serialize_lobby(updated_lobby.copy())
            }
        )
        
        # Also publish lobby_updated for reliable state sync
        publish_lobby_event(
            code,
            EventType.LOBBY_UPDATED,
            {"lobby": serialize_lobby(updated_lobby.copy())}
        )

        logger.info("player_joined code=%s player=%s", code, user["username"])
        return jsonify({
            "lobby": serialize_lobby(updated_lobby),
            "code": code
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("join_lobby_failed error=%s", e, exc_info=True)
        return jsonify({"error": "Failed to join lobby"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>/leave", methods=["POST"])
@multiplayer_authenticated
def leave_lobby(lobby_code: str):
    """Leave a lobby.

    Args:
        lobby_code: The 6-character lobby code.

    Returns:
        JSON confirmation of leaving.
    """
    try:
        user = g.user
        user_id = str(user["_id"])
        lobby_code = lobby_code.upper()

        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        # Remove the player
        updated_lobby = lobby_repository.remove_player_from_lobby(lobby_code, user_id)

        result = {"deleted": False, "new_creator_id": None}

        if not updated_lobby or not updated_lobby.get("players"):
            # Empty lobby, delete it
            lobby_repository.delete_lobby(lobby_code)
            result["deleted"] = True

            # Publish lobby closed event
            publish_lobby_event(
                lobby_code,
                EventType.LOBBY_CLOSED,
                {"reason": "All players left"}
            )
        else:
            # Check if creator left
            if lobby["creator_id"] == user_id:
                # Reassign creator to first remaining player
                new_creator = updated_lobby["players"][0]
                lobby_repository.reassign_creator(lobby_code, new_creator["user_id"])
                result["new_creator_id"] = new_creator["user_id"]

            # Publish player left event
            publish_lobby_event(
                lobby_code,
                EventType.PLAYER_LEFT,
                {
                    "user_id": user_id,
                    "username": user["username"],
                    "new_creator_id": result.get("new_creator_id"),
                    "lobby": serialize_lobby(updated_lobby.copy()) if not result["deleted"] else None
                }
            )

        logger.info("player_left code=%s player=%s deleted=%s", lobby_code, user["username"], result["deleted"])
        return jsonify({"success": True, **result}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("leave_lobby_failed code=%s error=%s", lobby_code, e, exc_info=True)
        return jsonify({"error": "Failed to leave lobby"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>/ready", methods=["POST"])
@multiplayer_authenticated
def toggle_ready(lobby_code: str):
    """Toggle player ready status.

    Args:
        lobby_code: The 6-character lobby code.

    Request Body:
        {
            "ready": true  # Required, boolean ready state
        }

    Returns:
        JSON with updated lobby and all_ready flag.
    """
    try:
        user = g.user
        user_id = str(user["_id"])
        lobby_code = lobby_code.upper()

        data = request.get_json() or {}
        ready = data.get("ready", False)

        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        # Check if player is in lobby
        is_player = any(p["user_id"] == user_id for p in lobby["players"])
        if not is_player:
            return jsonify({"error": "You are not in this lobby"}), 400

        # Update ready status
        updated_lobby = lobby_repository.update_player_ready_status(lobby_code, user_id, ready)

        # Check if all players are ready
        all_ready = lobby_repository.is_all_players_ready(lobby_code)

        # Publish ready status event
        publish_lobby_event(
            lobby_code,
            EventType.PLAYER_READY,
            {
                "user_id": user_id,
                "username": user["username"],
                "ready": ready,
                "all_ready": all_ready,
                "lobby": serialize_lobby(updated_lobby.copy())
            }
        )
        
        # Also publish lobby_updated for reliable state sync
        publish_lobby_event(
            lobby_code,
            EventType.LOBBY_UPDATED,
            {"lobby": serialize_lobby(updated_lobby.copy())}
        )

        # If all ready, also publish that event
        if all_ready:
            publish_lobby_event(
                lobby_code,
                EventType.ALL_PLAYERS_READY,
                {"lobby": serialize_lobby(updated_lobby.copy())}
            )

        logger.info("player_ready code=%s player=%s ready=%s all_ready=%s",
                    lobby_code, user["username"], ready, all_ready)

        return jsonify({
            "lobby": serialize_lobby(updated_lobby),
            "all_ready": all_ready
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("toggle_ready_failed code=%s error=%s", lobby_code, e, exc_info=True)
        return jsonify({"error": "Failed to update ready status"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>/settings", methods=["PATCH"])
@multiplayer_authenticated
def update_lobby_settings(lobby_code: str):
    """Update lobby settings (creator only, before game starts).

    Args:
        lobby_code: The 6-character lobby code.

    Request Body:
        {
            "categories": ["Science"],           # Optional
            "difficulty": 2,                     # Optional
            "question_timer": 45,                # Optional
            "question_count": 10,                # Optional
            "max_players": 10                    # Optional
        }

    Returns:
        JSON with updated lobby details.
    """
    try:
        user = g.user
        user_id = str(user["_id"])
        lobby_code = lobby_code.upper()

        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        # Only creator can update settings
        if lobby["creator_id"] != user_id:
            return jsonify({"error": "Only the lobby creator can update settings"}), 403

        # Can't update settings after game starts
        if lobby["status"] != "waiting":
            return jsonify({"error": "Cannot update settings after game has started"}), 400

        data = request.get_json() or {}

        # Extract optional settings
        categories = data.get("categories")
        difficulty = data.get("difficulty")
        question_timer = data.get("question_timer")
        max_players = data.get("max_players")

        # Validate if provided
        if difficulty is not None and difficulty not in [1, 2, 3]:
            return jsonify({"error": "Difficulty must be 1, 2, or 3"}), 400
            
        if max_players is not None and len(lobby["players"]) > max_players:
            return jsonify({
                "error": f"Cannot reduce max players below current player count ({len(lobby['players'])})"
            }), 400

        # Extract question_list for new Step 5 implementation
        question_list = data.get("question_list")

        # Update settings
        updated_lobby = lobby_repository.update_settings(
            lobby_code,
            categories=categories,
            difficulty=difficulty,
            question_timer=question_timer,
            max_players=max_players,
            question_list=question_list
        )

        # Publish settings updated event (single event, no duplication)
        publish_lobby_event(
            lobby_code,
            EventType.SETTINGS_UPDATED,
            {"lobby": serialize_lobby(updated_lobby.copy())}
        )

        logger.info("settings_updated code=%s by=%s", lobby_code, user["username"])

        return jsonify({"lobby": serialize_lobby(updated_lobby)}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("update_settings_failed code=%s error=%s", lobby_code, e, exc_info=True)
        return jsonify({"error": "Failed to update settings"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>/start", methods=["POST"])
@multiplayer_authenticated
def start_game(lobby_code: str):
    """Start the game (creator only).

    Args:
        lobby_code: The 6-character lobby code.

    Returns:
        JSON with game session info.
    """
    try:
        user = g.user
        user_id = str(user["_id"])
        lobby_code = lobby_code.upper()

        # Rate limiting for multiplayer game creation (daily reset at UTC midnight)
        # TEMPORARILY DISABLED FOR TESTING
        # from common.utils.rate_limiter import check_daily_rate_limit
        # from common.utils.config import settings
        
        # max_games = settings.rate_limit_multiplayer_games_max
        # allowed, remaining, reset_time = check_daily_rate_limit(
        #     user_id, "multiplayer_game_create", max_games
        # )
        
        # if not allowed:
        #     from datetime import datetime, timezone
        #     reset_datetime = datetime.fromtimestamp(reset_time, tz=timezone.utc)
        #     logger.warning(
        #         "rate_limit_exceeded_multiplayer_game user=%s remaining=%d reset_at_utc_midnight",
        #         user_id, remaining
        #     )
        #     return jsonify({
        #         "error": f"You can only start {max_games} multiplayer games per day. Resets at midnight UTC.",
        #         "limit": max_games,
        #         "reset_time": reset_time,
        #         "remaining": remaining,
        #     }), 429

        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503

        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404

        # Only creator can start
        if lobby["creator_id"] != user_id:
            return jsonify({"error": "Only the lobby creator can start the game"}), 403

        # Check player count
        if len(lobby["players"]) < settings.min_players_to_start:
            return jsonify({
                "error": f"Need at least {settings.min_players_to_start} players to start"
            }), 400

        # Check all ready
        if not lobby_repository.is_all_players_ready(lobby_code):
            return jsonify({"error": "Not all players are ready"}), 400

        # Validate question_list exists and is not empty
        question_list = lobby.get("question_list", [])
        if not question_list or len(question_list) == 0:
            return jsonify({"error": "No questions configured. Add questions before starting."}), 400

        # Get custom AI settings from request headers to forward to multiplayer
        custom_api_key = request.headers.get("X-OpenAI-API-Key")
        custom_model = request.headers.get("X-OpenAI-Model")
        
        logger.info("start_game_headers code=%s has_api_key=%s has_model=%s",
                    lobby_code, "yes" if custom_api_key else "no", "yes" if custom_model else "no")

        # Update status to countdown
        lobby_repository.update_lobby_status(lobby_code, "countdown")

        # Publish game starting event with AI settings
        publish_lobby_event(
            lobby_code,
            EventType.GAME_STARTING,
            {
                "lobby": serialize_lobby(lobby.copy()),
                "countdown_seconds": 3,  # Default countdown
                "ai_settings": {
                    "api_key": custom_api_key,
                    "model": custom_model,
                } if custom_api_key else None
            }
        )

        logger.info("game_starting code=%s creator=%s players=%d",
                    lobby_code, user["username"], len(lobby["players"]))

        return jsonify({
            "success": True,
            "status": "countdown",
            "lobby": serialize_lobby(lobby)
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("start_game_failed code=%s error=%s", lobby_code, e, exc_info=True)
        return jsonify({"error": "Failed to start game"}), 500


@multiplayer_bp.route("/game-session/create", methods=["POST"])
def create_game_session():
    """Create a game session and generate questions for multiplayer game.
    
    This is called by the multiplayer WebSocket server with internal authentication.
    Requires X-Internal-Secret header matching INTERNAL_SERVICE_SECRET env var.
    
    Request Body:
        {
            "lobby_code": "ABC123",
            "question_list": [
                {"category": "Git", "subject": "Basics", "difficulty": 2, "count": 1}
            ]
        }
    
    Returns:
        JSON with session_id and questions array.
    """
    try:
        # Verify internal service authentication
        import os
        internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        request_secret = request.headers.get("X-Internal-Secret")
        
        if not internal_secret:
            logger.error("INTERNAL_SERVICE_SECRET not configured")
            return jsonify({"error": "Service misconfigured"}), 503
            
        if not request_secret or request_secret != internal_secret:
            logger.warning("invalid_internal_secret remote_addr=%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        lobby_code = data.get("lobby_code", "").upper()
        question_list = data.get("question_list", [])
        
        if not lobby_code:
            return jsonify({"error": "lobby_code is required"}), 400
        if not question_list:
            return jsonify({"error": "question_list is required"}), 400
        
        lobby_repository = get_lobby_repository()
        questions_repository = get_questions_repository()
        quiz_repository = get_quiz_repository()
        
        if not all([lobby_repository, questions_repository, quiz_repository]):
            return jsonify({"error": "Service not initialized"}), 503
        
        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404
        
        # Get custom AI settings from request headers (same as single-player)
        custom_api_key = request.headers.get("X-OpenAI-API-Key")
        custom_model = request.headers.get("X-OpenAI-Model")
        
        # Generate questions based on question_list
        from common.utils.ai.service import AIQuestionService
        ai_service = AIQuestionService()
        
        questions = []
        total_expected = sum(qs.get("count", 1) for qs in question_list)
        
        for question_set in question_list:
            category = question_set.get("category")
            subject = question_set.get("subject")  # This is the subcategory
            difficulty = question_set.get("difficulty", lobby.get("difficulty", 2))
            count = question_set.get("count", 1)
            
            for i in range(count):
                try:
                    # Get random keyword and style modifier for variety (like singleplayer)
                    keyword = quiz_controller.get_random_keyword(category, subject)
                    style_modifier = quiz_controller.get_random_style_modifier(category, subject)
                    
                    # No fallbacks - should raise error if keywords/style_modifiers missing
                    if not keyword:
                        raise ValueError(f"No keywords found for category={category} subject={subject}")
                    if not style_modifier:
                        raise ValueError(f"No style_modifiers found for category={category} subject={subject}")
                    
                    question_data = ai_service.generate_multiplayer_question(
                        category=category,
                        subcategory=subject,
                        keyword=keyword,
                        difficulty=difficulty,
                        style_modifier=style_modifier,
                        custom_api_key=custom_api_key,
                        custom_model=custom_model,
                    )
                    questions.append({
                        "question_text": question_data["question"],
                        "options": question_data["options"],
                        "correct_answer": question_data["correct_answer"],
                        "category": category,
                        "subcategory": subject,
                        "difficulty": difficulty
                    })
                except Exception as e:
                    logger.error(
                        "generate_question_failed category=%s subject=%s difficulty=%d "
                        "question=%d/%d total_generated=%d/%d error=%s",
                        category, subject, difficulty, i+1, count, 
                        len(questions), total_expected, str(e)
                    )
                    # Fail fast - don't create broken game session
                    return jsonify({
                        "error": f"Failed to generate question {len(questions)+1}/{total_expected} for {category}/{subject}: {str(e)}"
                    }), 500
        
        # Create game session document
        from datetime import datetime, timezone
        session_doc = {
            "lobby_id": lobby["_id"],
            "lobby_code": lobby_code,
            "questions": questions,
            "current_question_index": -1,
            "question_start_time": None,
            "player_answers": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = get_db_controller().get_collection("multiplayer_game_sessions").insert_one(session_doc)
        session_id = str(result.inserted_id)
        
        logger.info("game_session_created session_id=%s lobby=%s questions=%d",
                    session_id, lobby_code, len(questions))
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "questions": questions,
            "total_questions": len(questions)
        }), 200
        
    except Exception as e:
        logger.error("create_game_session_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to create game session: {str(e)}"}), 500


@multiplayer_bp.route("/game-action/submit-answer", methods=["POST"])
def submit_answer():
    """Record a player's answer to a question.
    
    Internal endpoint called by multiplayer WebSocket server.
    Requires X-Internal-Secret header.
    
    Request Body:
        {
            "lobby_code": "ABC123",
            "user_id": "507f1f77bcf86cd799439011",
            "answer": "Option A",
            "time_taken": 5.3
        }
    
    Returns:
        JSON with is_correct, points_earned, and total_score.
    """
    try:
        # Verify internal service authentication
        import os
        internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        request_secret = request.headers.get("X-Internal-Secret")
        
        if not internal_secret or not request_secret or request_secret != internal_secret:
            logger.warning("invalid_internal_secret_submit_answer remote_addr=%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        lobby_code = data.get("lobby_code", "").upper()
        user_id = data.get("user_id")
        answer = data.get("answer")
        time_taken = data.get("time_taken", 0)
        
        if not all([lobby_code, user_id, answer is not None]):
            return jsonify({"error": "lobby_code, user_id, and answer are required"}), 400
        
        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503
        
        # Get game session and lobby
        from bson import ObjectId
        game_sessions = get_db_controller().get_collection("multiplayer_game_sessions")
        session = game_sessions.find_one({"lobby_code": lobby_code})
        
        if not session:
            return jsonify({"error": "Game session not found"}), 404
        
        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404
        
        current_index = session["current_question_index"]
        if current_index < 0 or current_index >= len(session["questions"]):
            return jsonify({"error": "No active question"}), 400
        
        # Check if already answered
        player_answers = session.get("player_answers", {}).get(user_id, [])
        if any(a["question_index"] == current_index for a in player_answers):
            return jsonify({"error": "Already answered this question"}), 400
        
        # Calculate score
        current_question = session["questions"][current_index]
        is_correct = (answer == current_question["correct_answer"])
        
        if is_correct:
            base_points = 1000
            time_ratio = min(time_taken / lobby["question_timer"], 1.0)
            time_multiplier = 1 - (time_ratio * 0.5)
            points = max(int(base_points * time_multiplier), 500)
        else:
            points = 0
        
        # Record answer
        answer_record = {
            "question_index": current_index,
            "answer": answer,
            "time_taken": time_taken,
            "is_correct": is_correct,
            "points": points
        }
        
        game_sessions.update_one(
            {"_id": session["_id"]},
            {"$push": {f"player_answers.{user_id}": answer_record}}
        )
        
        # Calculate total score
        all_answers = player_answers + [answer_record]
        total_score = sum(a["points"] for a in all_answers)
        
        # Update player score in lobby for real-time leaderboard
        update_result = lobby_repository.update_player_score(lobby_code, user_id, total_score)
        logger.info("update_player_score lobby=%s user=%s score=%d success=%s", 
                   lobby_code, user_id, total_score, update_result)
        
        # CRITICAL: Also update Redis game_state.player_scores so game loop has accurate scores
        from common.redis_client import get_redis_client, EventType
        redis_client = get_redis_client()
        
        # Update Redis game state with new score
        game_state = redis_client.get_game_state(lobby_code)
        if game_state:
            player_scores = game_state.get('player_scores', {})
            player_scores[user_id] = total_score
            game_state['player_scores'] = player_scores
            redis_client.set_game_state(lobby_code, game_state, ttl_seconds=3600)
            logger.info("redis_game_state_score_updated lobby=%s user=%s score=%d", 
                       lobby_code, user_id, total_score)
        
        # Get updated lobby with all player scores
        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if lobby:
            standings = []
            for player in lobby.get('players', []):
                standings.append({
                    "user_id": player['user_id'],
                    "username": player['username'],
                    "score": player.get('score', 0)
                })
            standings.sort(key=lambda x: x['score'], reverse=True)
            
            redis_client.publish_lobby_event(
                lobby_code,
                EventType.SCORES_UPDATED,
                {"standings": standings}
            )
        
        logger.info("answer_recorded lobby=%s user=%s correct=%s points=%d total=%d",
                   lobby_code, user_id, is_correct, points, total_score)
        
        response_data = {
            "success": True,
            "is_correct": is_correct,
            "points_earned": points,
            "total_score": total_score,
            "correct_answer": current_question["correct_answer"]
        }
        logger.info("submit_answer_response lobby=%s data=%s", lobby_code, response_data)
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error("submit_answer_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to submit answer: {str(e)}"}), 500


@multiplayer_bp.route("/game-action/record-auto-fail", methods=["POST"])
def record_auto_fail():
    """Record auto-fail for players who didn't answer in time.
    
    Internal endpoint called by multiplayer WebSocket server.
    Requires X-Internal-Secret header.
    
    Request Body:
        {
            "lobby_code": "ABC123",
            "user_id": "507f1f77bcf86cd799439011",
            "question_index": 0
        }
    
    Returns:
        JSON with success status.
    """
    try:
        # Verify internal service authentication
        import os
        internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        request_secret = request.headers.get("X-Internal-Secret")
        
        if not internal_secret or not request_secret or request_secret != internal_secret:
            logger.warning("invalid_internal_secret_auto_fail remote_addr=%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        lobby_code = data.get("lobby_code", "").upper()
        user_id = data.get("user_id")
        question_index = data.get("question_index")
        
        if not all([lobby_code, user_id, question_index is not None]):
            return jsonify({"error": "lobby_code, user_id, and question_index are required"}), 400
        
        # Get game session
        game_sessions = get_db_controller().get_collection("multiplayer_game_sessions")
        session = game_sessions.find_one({"lobby_code": lobby_code})
        
        if not session:
            return jsonify({"error": "Game session not found"}), 404
        
        # Check if already answered
        player_answers = session.get("player_answers", {}).get(user_id, [])
        if any(a["question_index"] == question_index for a in player_answers):
            # Already answered, skip
            return jsonify({"success": True, "skipped": True}), 200
        
        # Record auto-fail
        answer_record = {
            "question_index": question_index,
            "answer": "",
            "time_taken": 0,
            "is_correct": False,
            "points": 0
        }
        
        game_sessions.update_one(
            {"_id": session["_id"]},
            {"$push": {f"player_answers.{user_id}": answer_record}}
        )
        
        logger.info("auto_fail_recorded lobby=%s user=%s question=%d",
                   lobby_code, user_id, question_index)
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        logger.error("record_auto_fail_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to record auto-fail: {str(e)}"}), 500


@multiplayer_bp.route("/lobby/<lobby_code>/update-score", methods=["POST"])
def update_player_score(lobby_code):
    """Update player score in MongoDB during game.
    
    Internal endpoint called by multiplayer WebSocket server.
    Requires X-Internal-Secret header.
    
    Request Body:
        {
            "user_id": "user123",
            "score": 144
        }
    
    Returns:
        JSON with success status.
    """
    try:
        # Verify internal service authentication
        import os
        internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        request_secret = request.headers.get("X-Internal-Secret")
        
        if not internal_secret or not request_secret or request_secret != internal_secret:
            logger.warning("invalid_internal_secret_update_score remote_addr=%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        user_id = data.get("user_id")
        score = data.get("score")
        
        if not user_id or score is None:
            return jsonify({"error": "user_id and score are required"}), 400
        
        lobby_code = lobby_code.upper()
        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503
        
        # Update score in MongoDB
        result = lobby_repository.collection.update_one(
            {"lobby_code": lobby_code, "players.user_id": user_id},
            {"$set": {"players.$.score": score}}
        )
        
        if result.matched_count == 0:
            logger.warning("update_score_no_match lobby=%s user=%s", lobby_code, user_id)
            return jsonify({"error": "Player not found in lobby"}), 404
        
        logger.info("score_updated_in_db lobby=%s user=%s score=%d", lobby_code, user_id, score)
        return jsonify({"success": True}), 200
        
    except Exception as e:
        logger.error("update_score_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to update score: {str(e)}"}), 500


@multiplayer_bp.route("/game-action/finalize", methods=["POST"])
def finalize_game():
    """Finalize game, award XP, and return final rankings.
    
    Internal endpoint called by multiplayer WebSocket server.
    Requires X-Internal-Secret header.
    
    Request Body:
        {
            "lobby_code": "ABC123",
            "player_scores": {"user_id1": 5000, "user_id2": 3500}
        }
    
    Returns:
        JSON with rankings and xp_awarded.
    """
    try:
        # Verify internal service authentication
        import os
        internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        request_secret = request.headers.get("X-Internal-Secret")
        
        if not internal_secret or not request_secret or request_secret != internal_secret:
            logger.warning("invalid_internal_secret_finalize remote_addr=%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        lobby_code = data.get("lobby_code", "").upper()
        player_scores = data.get("player_scores", {})
        correct_answers = data.get("correct_answers", {})
        
        if not lobby_code:
            return jsonify({"error": "lobby_code is required"}), 400
        
        lobby_repository = get_lobby_repository()
        if not lobby_repository:
            return jsonify({"error": "Service not initialized"}), 503
        
        lobby = lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            return jsonify({"error": "Lobby not found"}), 404
        
        # Get game session for question count
        game_sessions = get_db_controller().get_collection("multiplayer_game_sessions")
        session = game_sessions.find_one({"lobby_code": lobby_code})
        question_count = len(session["questions"]) if session else 0
        
        # Calculate XP and rankings
        # XP algorithm: score/10 + winner_bonus
        # Winner bonus = 10 * (player_count - 1)
        player_count = len(player_scores)
        winner_bonus = 10 * (player_count - 1) if player_count > 1 else 0
        
        ranked_players = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
        
        xp_awarded = {}
        rankings = []
        
        multiplayer_xp_col = get_db_controller().get_collection("multiplayer_xp")
        
        for rank, (user_id, score) in enumerate(ranked_players, start=1):
            # Calculate XP: score/10 + winner_bonus (for 1st place only)
            base_xp = int(score / 10)
            xp = base_xp + winner_bonus if rank == 1 else base_xp
            
            # Award XP to user
            from datetime import datetime, timezone
            from bson import ObjectId
            
            multiplayer_xp_col.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$inc": {"total_xp": xp, "games_played": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                    "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
                },
                upsert=True
            )
            
            # Also add XP to user's main profile
            user_repo = get_user_repository()
            if user_repo:
                user_repo.add_bonus_xp(user_id, xp)
                logger.debug("added_xp_to_profile user=%s xp=%d", user_id, xp)
            
            xp_awarded[user_id] = xp
            
            # Build ranking entry
            player = next((p for p in lobby["players"] if p["user_id"] == user_id), None)
            if player:
                rankings.append({
                    "rank": rank,
                    "user_id": user_id,
                    "username": player["username"],
                    "score": score,
                    "xp_earned": xp,
                    "correct_answers": correct_answers.get(user_id, 0)
                })
        
        # Update lobby status
        lobby_repository.update_lobby_status(lobby_code, "completed")
        
        logger.info("game_finalized lobby=%s players=%d winner=%s",
                   lobby_code, len(rankings), 
                   rankings[0]["username"] if rankings else "none")
        
        return jsonify({
            "success": True,
            "rankings": rankings,
            "xp_awarded": xp_awarded
        }), 200
        
    except Exception as e:
        logger.error("finalize_game_failed error=%s", e, exc_info=True)
        return jsonify({"error": f"Failed to finalize game: {str(e)}"}), 500


@multiplayer_bp.route("/history", methods=["GET"])
@multiplayer_authenticated
def get_multiplayer_history():
    """Get user's multiplayer game history.

    Query Parameters:
        limit: Number of games to return (default: 20)

    Returns:
        JSON list of past multiplayer games.
    """
    try:
        user = g.user
        limit = request.args.get("limit", 20, type=int)

        # TODO: Implement history from game_sessions collection
        # For now, return empty list
        history = []

        return jsonify({"history": history}), 200

    except Exception as e:
        logger.error("get_history_failed error=%s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch history"}), 500


def init_multiplayer_routes(lobby_repository, quiz_repository) -> Blueprint:
    """Initialize multiplayer routes with dependencies.

    Args:
        lobby_repository: LobbyRepository instance
        quiz_repository: QuizRepository instance

    Returns:
        Configured blueprint
    """
    global quiz_controller
    quiz_controller = QuizController(quiz_repository)
    
    # Dependencies are stored in app.extensions by the app factory
    # This function is kept for consistency with other route modules
    return multiplayer_bp

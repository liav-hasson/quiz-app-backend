"""Repository for managing multiplayer lobbies.

This repository handles all MongoDB operations for the multiplayer_lobbies collection.
Used by the API server for CRUD operations.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from common.repositories.base_repository import BaseRepository
from common.utils.config import settings


class LobbyRepository(BaseRepository):
    """Persistence layer for the `multiplayer_lobbies` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "multiplayer_lobbies")

    def ensure_indexes(self) -> None:
        """Create unique index on lobby_code and TTL index on expire_at."""
        self.collection.create_index("lobby_code", unique=True)
        self.collection.create_index("expire_at", expireAfterSeconds=0)

    def _generate_lobby_code(self) -> str:
        """Generate a unique 6-character alphanumeric code."""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=settings.lobby_code_length))
            if not self.collection.find_one({"lobby_code": code}):
                return code

    def create_lobby(
        self,
        creator_user: Dict[str, Any],
        categories: List[str],
        difficulty: int,
        question_timer: int,
        max_players: int,
    ) -> Dict[str, Any]:
        """Create a new lobby."""
        code = self._generate_lobby_code()
        now = datetime.now()
        
        # Initialize question_list as empty - host will add questions via settings
        # This is the new primary way to configure questions
        lobby_doc = {
            "lobby_code": code,
            "creator_id": str(creator_user["_id"]),
            "creator_username": creator_user["username"],
            "categories": categories,  # Keep for backwards compatibility
            "difficulty": difficulty,  # Keep for backwards compatibility
            "question_timer": question_timer,
            "max_players": max_players,
            "question_list": [],  # Primary source - host adds questions
            "players": [
                {
                    "user_id": str(creator_user["_id"]),
                    "username": creator_user["username"],
                    "picture": creator_user.get("profile_picture", ""),
                    "ready": False,
                    "score": 0,
                    "connected": True
                }
            ],
            "status": "waiting",
            "created_at": now,
            "updated_at": now,
            "expire_at": now + timedelta(hours=settings.lobby_expiry_hours)
        }
        
        self.collection.insert_one(lobby_doc)
        # Return the doc with _id as string
        lobby_doc["_id"] = str(lobby_doc["_id"])
        return lobby_doc

    def get_lobby_by_code(self, lobby_code: str) -> Optional[Dict[str, Any]]:
        """Get a lobby by its code."""
        lobby = self.collection.find_one({"lobby_code": lobby_code.upper()})
        if lobby:
            lobby["_id"] = str(lobby["_id"])
        return lobby

    def add_player_to_lobby(self, lobby_code: str, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a player to the lobby if not full."""
        lobby = self.get_lobby_by_code(lobby_code)
        if not lobby:
            raise ValueError("Lobby not found")
            
        if len(lobby["players"]) >= lobby["max_players"]:
            raise ValueError("Lobby is full")
            
        # Check if player already exists
        for player in lobby["players"]:
            if player["user_id"] == str(user["_id"]):
                # Update connection status if rejoining
                self.collection.update_one(
                    {"lobby_code": lobby_code.upper(), "players.user_id": str(user["_id"])},
                    {"$set": {"players.$.connected": True}}
                )
                return self.get_lobby_by_code(lobby_code)

        new_player = {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "picture": user.get("profile_picture", ""),
            "ready": False,
            "score": 0,
            "connected": True
        }
        
        self.collection.update_one(
            {"lobby_code": lobby_code.upper()},
            {
                "$push": {"players": new_player},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def remove_player_from_lobby(self, lobby_code: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove a player from the lobby."""
        self.collection.update_one(
            {"lobby_code": lobby_code.upper()},
            {
                "$pull": {"players": {"user_id": user_id}},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def update_player_ready_status(self, lobby_code: str, user_id: str, ready: bool) -> Optional[Dict[str, Any]]:
        """Update a player's ready status."""
        self.collection.update_one(
            {"lobby_code": lobby_code.upper(), "players.user_id": user_id},
            {
                "$set": {
                    "players.$.ready": ready,
                    "updated_at": datetime.now()
                }
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def update_lobby_status(self, lobby_code: str, status: str) -> bool:
        """Update the lobby status (waiting, countdown, in_progress, completed)."""
        result = self.collection.update_one(
            {"lobby_code": lobby_code.upper()},
            {"$set": {"status": status, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0

    def is_all_players_ready(self, lobby_code: str) -> bool:
        """Check if all players in the lobby are ready."""
        lobby = self.get_lobby_by_code(lobby_code)
        if not lobby or not lobby["players"]:
            return False
        return all(p["ready"] for p in lobby["players"])

    def update_player_score(self, lobby_code: str, user_id: str, score: int) -> bool:
        """Update a player's score."""
        result = self.collection.update_one(
            {"lobby_code": lobby_code.upper(), "players.user_id": user_id},
            {"$set": {"players.$.score": score}}
        )
        return result.modified_count > 0

    def get_active_lobbies(self) -> List[Dict[str, Any]]:
        """Get all active (waiting) lobbies."""
        cursor = self.collection.find({"status": "waiting"}).sort("created_at", -1).limit(20)
        lobbies = list(cursor)
        for lobby in lobbies:
            lobby["_id"] = str(lobby["_id"])
        return lobbies

    def reassign_creator(self, lobby_code: str, new_creator_id: str) -> bool:
        """Reassign the lobby creator when the original creator leaves."""
        lobby = self.get_lobby_by_code(lobby_code)
        if not lobby:
            return False
            
        new_creator = next((p for p in lobby["players"] if p["user_id"] == new_creator_id), None)
        if not new_creator:
            return False
            
        result = self.collection.update_one(
            {"lobby_code": lobby_code.upper()},
            {
                "$set": {
                    "creator_id": new_creator_id,
                    "creator_username": new_creator["username"],
                    "updated_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0

    def delete_lobby(self, lobby_code: str) -> bool:
        """Delete a lobby."""
        result = self.collection.delete_one({"lobby_code": lobby_code.upper()})
        return result.deleted_count > 0

    def set_game_session_id(self, lobby_code: str, session_id: str) -> bool:
        """Set the game session ID for a lobby that has started."""
        result = self.collection.update_one(
            {"lobby_code": lobby_code.upper()},
            {
                "$set": {
                    "game_session_id": session_id,
                    "updated_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0

    def update_settings(
        self,
        lobby_code: str,
        categories: Optional[List[str]] = None,
        difficulty: Optional[int] = None,
        question_timer: Optional[int] = None,
        max_players: Optional[int] = None,
        question_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update lobby settings (creator only, before game starts).
        
        Args:
            lobby_code: The 6-character lobby code
            categories: List of category names (optional)
            difficulty: Difficulty level 1-3 (optional)
            question_timer: Timer in seconds (optional)
            max_players: Maximum player count (optional)
            question_list: List of question sets with metadata (primary source for questions)
            
        Returns:
            Updated lobby document or None if not found
        """
        update_doc = {"updated_at": datetime.now()}
        
        if categories is not None:
            update_doc["categories"] = categories
        if difficulty is not None:
            update_doc["difficulty"] = difficulty
        if question_timer is not None:
            update_doc["question_timer"] = question_timer
        if max_players is not None:
            update_doc["max_players"] = max_players
        if question_list is not None:
            update_doc["question_list"] = question_list
        
        result = self.collection.find_one_and_update(
            {"lobby_code": lobby_code.upper()},
            {"$set": update_doc},
            return_document=True
        )
        
        if result:
            result["_id"] = str(result["_id"])
        return result

"""Repository for managing multiplayer lobbies."""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

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
        
        lobby_doc = {
            "lobby_code": code,
            "creator_id": str(creator_user["_id"]),
            "creator_username": creator_user["username"],
            "categories": categories,
            "difficulty": difficulty,
            "question_timer": question_timer,
            "max_players": max_players,
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
        lobby = self.collection.find_one({"lobby_code": lobby_code})
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
                    {"lobby_code": lobby_code, "players.user_id": str(user["_id"])},
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
            {"lobby_code": lobby_code},
            {
                "$push": {"players": new_player},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def remove_player_from_lobby(self, lobby_code: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove a player from the lobby."""
        self.collection.update_one(
            {"lobby_code": lobby_code},
            {
                "$pull": {"players": {"user_id": user_id}},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def update_player_ready_status(self, lobby_code: str, user_id: str, ready: bool) -> Optional[Dict[str, Any]]:
        self.collection.update_one(
            {"lobby_code": lobby_code, "players.user_id": user_id},
            {
                "$set": {
                    "players.$.ready": ready,
                    "updated_at": datetime.now()
                }
            }
        )
        return self.get_lobby_by_code(lobby_code)

    def update_lobby_status(self, lobby_code: str, status: str) -> bool:
        result = self.collection.update_one(
            {"lobby_code": lobby_code},
            {"$set": {"status": status, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0

    def is_all_players_ready(self, lobby_code: str) -> bool:
        lobby = self.get_lobby_by_code(lobby_code)
        if not lobby or not lobby["players"]:
            return False
        return all(p["ready"] for p in lobby["players"])

    def update_player_score(self, lobby_code: str, user_id: str, score: int) -> bool:
        result = self.collection.update_one(
            {"lobby_code": lobby_code, "players.user_id": user_id},
            {"$set": {"players.$.score": score}}
        )
        return result.modified_count > 0

    def get_active_lobbies(self) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"status": "waiting"}).sort("created_at", -1).limit(20)
        lobbies = list(cursor)
        for lobby in lobbies:
            lobby["_id"] = str(lobby["_id"])
        return lobbies

    def reassign_creator(self, lobby_code: str, new_creator_id: str) -> bool:
        # Get username for new creator
        lobby = self.get_lobby_by_code(lobby_code)
        if not lobby:
            return False
            
        new_creator = next((p for p in lobby["players"] if p["user_id"] == new_creator_id), None)
        if not new_creator:
            return False
            
        result = self.collection.update_one(
            {"lobby_code": lobby_code},
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
        result = self.collection.delete_one({"lobby_code": lobby_code})
        return result.deleted_count > 0

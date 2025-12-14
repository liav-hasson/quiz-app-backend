from typing import List, Dict, Any, Optional

from common.utils.config import settings
from server.models.repositories.lobby_repository import LobbyRepository
from common.repositories.quiz_repository import QuizRepository

class LobbyController:
    def __init__(self, lobby_repository: LobbyRepository, quiz_repository: QuizRepository):
        self.lobby_repository = lobby_repository
        self.quiz_repository = quiz_repository

    def create_lobby(
        self, 
        user: Dict[str, Any], 
        categories: List[str], 
        difficulty: int, 
        question_timer: int, 
        max_players: int
    ) -> Dict[str, Any]:
        # Validate inputs
        if not categories:
            raise ValueError("At least one category is required")
        
        # Validate categories exist
        valid_categories = self.quiz_repository.get_categories()
        for cat in categories:
            if cat not in valid_categories:
                # For now, allow it if DB is empty or just warn
                pass 

        if difficulty not in [1, 2, 3]:
            raise ValueError("Difficulty must be 1, 2, or 3")
            
        if max_players < 2 or max_players > 20:
            raise ValueError("Max players must be between 2 and 20")

        return self.lobby_repository.create_lobby(
            user, categories, difficulty, question_timer, max_players
        )

    def join_lobby(self, user: Dict[str, Any], lobby_code: str) -> Dict[str, Any]:
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            raise ValueError("Lobby not found")
            
        if lobby["status"] != "waiting":
            # Allow rejoining if already a player
            is_player = any(p["user_id"] == str(user["_id"]) for p in lobby["players"])
            if not is_player:
                raise ValueError("Game already in progress")
        
        return self.lobby_repository.add_player_to_lobby(lobby_code, user)

    def leave_lobby(self, user: Dict[str, Any], lobby_code: str) -> Dict[str, Any]:
        user_id = str(user["_id"])
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            raise ValueError("Lobby not found")
            
        # Remove player
        updated_lobby = self.lobby_repository.remove_player_from_lobby(lobby_code, user_id)
        
        result = {"deleted": False, "new_creator_id": None}
        
        if not updated_lobby or not updated_lobby["players"]:
            # Empty lobby, delete it
            self.lobby_repository.delete_lobby(lobby_code)
            result["deleted"] = True
        elif lobby["creator_id"] == user_id:
            # Creator left, reassign
            new_creator = updated_lobby["players"][0]
            self.lobby_repository.reassign_creator(lobby_code, new_creator["user_id"])
            result["new_creator_id"] = new_creator["user_id"]
            
        return result

    def toggle_ready(self, user: Dict[str, Any], lobby_code: str, ready: bool) -> Dict[str, Any]:
        return self.lobby_repository.update_player_ready_status(
            lobby_code, str(user["_id"]), ready
        )

    def check_all_ready(self, lobby_code: str) -> bool:
        return self.lobby_repository.is_all_players_ready(lobby_code)

    def validate_game_start(self, lobby_code: str, user_id: str) -> Dict[str, Any]:
        lobby = self.lobby_repository.get_lobby_by_code(lobby_code)
        if not lobby:
            raise ValueError("Lobby not found")
            
        if lobby["creator_id"] != user_id:
            raise ValueError("Only creator can start the game")

        min_players = settings.min_players_to_start or 1
        if len(lobby["players"]) < min_players:
            raise ValueError(f"Not enough players to start (need {min_players})")
            
        if not self.check_all_ready(lobby_code):
            raise ValueError("Not all players are ready")
            
        self.lobby_repository.update_lobby_status(lobby_code, "countdown")
        return lobby

    def mark_player_disconnected(self, user: Dict[str, Any], lobby_code: str):
        # Logic to mark player as disconnected (optional, for UI)
        # For now we might just leave them or have a 'connected' flag in player object
        pass

    def get_active_lobbies(self) -> List[Dict[str, Any]]:
        return self.lobby_repository.get_active_lobbies()

    def get_lobby_by_code(self, lobby_code: str) -> Optional[Dict[str, Any]]:
        return self.lobby_repository.get_lobby_by_code(lobby_code)

"""Repository for managing multiplayer XP and rewards."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from common.repositories.user_repository import UserRepository


class MultiplayerXPRepository:
    """Wrapper around UserRepository for multiplayer-specific XP logic."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def award_game_xp(
        self, 
        user_id: str, 
        final_score: int, 
        difficulty_multiplier: float, 
        question_count: int
    ) -> int:
        """
        Award XP to user after multiplayer game.
        Returns the amount of XP awarded.
        """
        # Calculate weighted XP
        weighted_xp = int(final_score * difficulty_multiplier)
        
        # Update user experience
        self.user_repository.update_user_experience(user_id, weighted_xp)
        
        # Increment questions count
        self.user_repository.increment_questions_count(user_id, question_count)
        
        return weighted_xp

    def record_game_completion(
        self, 
        user_id: str, 
        lobby_code: str, 
        final_score: int, 
        rank: int, 
        xp_earned: int
    ) -> None:
        """
        Optional: Log game history to user profile or separate collection.
        For now, this is a placeholder for future analytics.
        """
        pass

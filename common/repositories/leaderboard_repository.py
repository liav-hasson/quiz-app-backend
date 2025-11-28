"""Repository for leaderboard (top ten) documents."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_repository import BaseRepository


class LeaderboardRepository(BaseRepository):
    """Manages entries in the `top_ten` collection."""

    # Difficulty multipliers for weighted XP calculation
    DIFFICULTY_MULTIPLIERS = {
        1: 1.0,   # Easy
        2: 1.5,   # Medium
        3: 2.0,   # Hard
    }

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "top_ten")

    def add_or_update_entry(
        self, username: str, score: float, meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add or update a leaderboard entry with weighted XP calculation.
        
        The score should be calculated as: weighted_xp / attempts
        where weighted_xp = sum(score * difficulty_multiplier) across all attempts.
        
        Args:
            username: User identifier
            score: Weighted average score (already calculated with difficulty multipliers)
            meta: Additional metadata (exp, count, weighted_xp)
        """
        now = datetime.now()
        # Round up the score to avoid floats
        rounded_score = math.ceil(score) if score > 0 else 0
        
        self.collection.update_one(
            {"username": username},
            {
                "$set": {"score": rounded_score, "meta": meta or {}, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return True

    def get_top_ten(self) -> List[Dict[str, Any]]:
        """Get top 10 users with rank positions."""
        docs = list(self.collection.find({}).sort("score", -1).limit(10))
        for idx, doc in enumerate(docs):
            doc["_id"] = str(doc["_id"])
            doc["rank"] = idx + 1
        return docs

    def get_user_rank(self, username: str, user_score: float) -> Optional[int]:
        """Calculate user's rank based on their weighted score.
        
        Args:
            username: User identifier
            user_score: User's weighted average score
            
        Returns:
            Rank position (1-based), or None if user not found
        """
        # Count how many users have a higher score
        higher_count = self.collection.count_documents({
            "score": {"$gt": math.ceil(user_score)}
        })
        return higher_count + 1

    def get_total_ranked_users(self) -> int:
        """Get total number of users in leaderboard."""
        return self.collection.count_documents({})

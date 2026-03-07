"""Repository for daily challenge questions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DailyChallengeRepository(BaseRepository):
    """Persistence layer for the `daily_challenges` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "daily_challenges")

    @staticmethod
    def _today_key() -> str:
        """Return today's date as a string key in UTC (YYYY-MM-DD)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def get_today_challenge(self) -> Optional[Dict[str, Any]]:
        """Get today's daily challenge, or None if it hasn't been generated yet."""
        doc = self.collection.find_one({"date": self._today_key()})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def save_challenge(self, question: str) -> Dict[str, Any]:
        """Save a new daily challenge question. Returns the saved document."""
        date_key = self._today_key()
        doc = {
            "date": date_key,
            "question": question,
            "answers": [],
            "created_at": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    def save_user_answer(
        self,
        user_id: str,
        username: str,
        answer: str,
        score: float,
        feedback: str,
    ) -> bool:
        """Record a user's answer for today's challenge. Returns True on success."""
        date_key = self._today_key()
        entry = {
            "user_id": user_id,
            "username": username,
            "answer": answer,
            "score": score,
            "feedback": feedback,
            "answered_at": datetime.now(timezone.utc),
        }
        result = self.collection.update_one(
            {"date": date_key},
            {"$push": {"answers": entry}},
        )
        return result.modified_count > 0

    def get_user_answer_today(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Check if a user has already answered today's challenge."""
        date_key = self._today_key()
        doc = self.collection.find_one(
            {"date": date_key, "answers.user_id": user_id},
            {"answers.$": 1},
        )
        if doc and doc.get("answers"):
            return doc["answers"][0]
        return None

    def get_today_leaderboard(self, limit: int = 20) -> list:
        """Get today's leaderboard sorted by score descending."""
        date_key = self._today_key()
        doc = self.collection.find_one({"date": date_key})
        if not doc or not doc.get("answers"):
            return []

        answers = sorted(doc["answers"], key=lambda a: a.get("score", 0), reverse=True)
        return [
            {
                "username": a["username"],
                "score": a["score"],
                "answered_at": a.get("answered_at"),
            }
            for a in answers[:limit]
        ]

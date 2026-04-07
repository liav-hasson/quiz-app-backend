"""Repository for daily challenge questions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DailyChallengeRepository(BaseRepository):
    """Persistence layer for the `daily_challenges` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "daily_challenges")

    @staticmethod
    def _today_key() -> str:
        """Return today's date as a string key in Israel time (YYYY-MM-DD)."""
        return datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")

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

    # --- Streak tracking ---

    def _streak_collection(self):
        """Access the daily_streaks collection."""
        return self._db_controller.db["daily_streaks"]

    def get_user_streak(self, user_id: str) -> Dict[str, Any]:
        """Get a user's current daily challenge streak."""
        doc = self._streak_collection().find_one({"user_id": user_id})
        if not doc:
            # Backfill: if user answered today but has no streak doc (pre-refactor)
            if self.get_user_answer_today(user_id):
                new_streak = self.update_user_streak(user_id)
                return {"current_streak": new_streak, "max_streak": new_streak, "active": True}
            return {"current_streak": 0, "max_streak": 0, "active": False}

        today = self._today_key()
        yesterday = (datetime.now(ISRAEL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
        last_date = doc.get("last_completed_date", "")

        # Active if they answered today or yesterday (still have a chance today)
        active = last_date in (today, yesterday)

        return {
            "current_streak": doc.get("current_streak", 0) if active else 0,
            "max_streak": doc.get("max_streak", 0),
            "active": last_date == today,  # True only if answered today
        }

    def update_user_streak(self, user_id: str) -> int:
        """Update a user's streak after answering today's challenge. Returns new streak."""
        today = self._today_key()
        yesterday = (datetime.now(ISRAEL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
        col = self._streak_collection()

        doc = col.find_one({"user_id": user_id})

        if not doc:
            # First ever daily challenge
            col.insert_one({
                "user_id": user_id,
                "current_streak": 1,
                "max_streak": 1,
                "last_completed_date": today,
            })
            return 1

        last_date = doc.get("last_completed_date", "")

        if last_date == today:
            # Already updated today
            return doc.get("current_streak", 1)

        if last_date == yesterday:
            # Consecutive day — increment
            new_streak = doc.get("current_streak", 0) + 1
        else:
            # Streak broken — reset to 1
            new_streak = 1

        new_max = max(new_streak, doc.get("max_streak", 0))

        col.update_one(
            {"user_id": user_id},
            {"$set": {
                "current_streak": new_streak,
                "max_streak": new_max,
                "last_completed_date": today,
            }},
        )
        return new_streak

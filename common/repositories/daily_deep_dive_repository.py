"""Repository for daily deep dive articles."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DailyDeepDiveRepository(BaseRepository):
    """Persistence layer for the `daily_deep_dives` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "daily_deep_dives")

    @staticmethod
    def _today_key() -> str:
        """Return today's date as a string key in Israel time (YYYY-MM-DD)."""
        return datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")

    def get_today_article(self) -> Optional[Dict[str, Any]]:
        """Get today's deep dive article, or None if not yet generated."""
        doc = self.collection.find_one({"date": self._today_key()})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def save_placeholder(self) -> Dict[str, Any]:
        """Save a placeholder indicating article generation is in progress."""
        date_key = self._today_key()
        doc = {
            "date": date_key,
            "status": "generating",
            "created_at": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    def update_article_content(
        self,
        keyword: str,
        category: str,
        subject: str,
        content: str,
    ) -> None:
        """Update today's placeholder with the generated content."""
        date_key = self._today_key()
        self.collection.update_one(
            {"date": date_key},
            {"$set": {
                "keyword": keyword,
                "category": category,
                "subject": subject,
                "content": content,
                "status": "ready",
                "xp_claims": [],
            }},
        )

    def delete_today(self) -> int:
        """Delete today's article(s). Returns count deleted."""
        result = self.collection.delete_many({"date": self._today_key()})
        return result.deleted_count

    def save_article(
        self,
        keyword: str,
        category: str,
        subject: str,
        content: str,
    ) -> Dict[str, Any]:
        """Save a new deep dive article. Returns the saved document."""
        date_key = self._today_key()
        doc = {
            "date": date_key,
            "keyword": keyword,
            "category": category,
            "subject": subject,
            "content": content,
            "xp_claims": [],
            "created_at": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    def has_user_claimed_xp(self, user_id: str) -> bool:
        """Check if a user has already claimed XP for today's article."""
        date_key = self._today_key()
        doc = self.collection.find_one(
            {"date": date_key, "xp_claims": user_id},
            {"_id": 1},
        )
        return doc is not None

    def claim_xp(self, user_id: str) -> bool:
        """Record that a user claimed XP for today's article. Returns True on success."""
        date_key = self._today_key()
        result = self.collection.update_one(
            {"date": date_key, "xp_claims": {"$ne": user_id}},
            {"$push": {"xp_claims": user_id}},
        )
        return result.modified_count > 0

    def get_archive(self, limit: int = 10, skip: int = 0) -> List[Dict[str, Any]]:
        """Return past articles, newest first, excluding today."""
        today = self._today_key()
        cursor = (
            self.collection.find(
                {"date": {"$ne": today}},
                {"xp_claims": 0},  # exclude xp_claims from archive results
            )
            .sort("date", -1)
            .skip(skip)
            .limit(limit)
        )
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    def get_archive_count(self) -> int:
        """Return the total number of archived articles (excluding today)."""
        today = self._today_key()
        return self.collection.count_documents({"date": {"$ne": today}})

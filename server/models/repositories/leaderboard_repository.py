"""Repository for leaderboard (top ten) documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_repository import BaseRepository


class LeaderboardRepository(BaseRepository):
    """Manages entries in the `top_ten` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "top_ten")

    def add_or_update_entry(
        self, username: str, score: float, meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        now = datetime.now()
        self.collection.update_one(
            {"username": username},
            {
                "$set": {"score": score, "meta": meta or {}, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return True

    def get_top_ten(self) -> List[Dict[str, Any]]:
        docs = list(self.collection.find({}).sort("score", -1).limit(10))
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

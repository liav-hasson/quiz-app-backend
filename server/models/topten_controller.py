from datetime import datetime
from typing import Dict, Any, List, Optional

from .dbcontroller import DBController


class TopTenController:
    """Controller for managing top-ten leaderboard entries."""

    def __init__(self, db_controller: DBController):
        self.db_controller = db_controller
        self.collection_name = "top_ten"
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            if self.db_controller.db is None:
                raise Exception(
                    "Database not connected. Call db_controller.connect() first."
                )
            self.collection = self.db_controller.get_collection(self.collection_name)
        return self.collection

    def add_or_update_entry(
        self, username: str, score: int, meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        collection = self._get_collection()
        now = datetime.now()
        collection.update_one(
            {"username": username},
            {
                "$set": {"score": score, "meta": meta or {}, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return True

    def get_top_ten(self) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        docs = list(collection.find({}).sort("score", -1).limit(10))
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

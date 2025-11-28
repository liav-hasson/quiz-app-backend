"""Repository for storing generated questions and user answers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId  # type: ignore
from bson.errors import InvalidId

from .base_repository import BaseRepository


class QuestionsRepository(BaseRepository):
    """Persistence layer for the `questions` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "questions")

    def add_question(
        self,
        user_id: str,
        username: str,
        question_text: str,
        keyword: str,
        category: str,
        subject: str,
        difficulty: int,
        ai_generated: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        doc = {
            "user_id": user_id,
            "username": username,
            "question_text": question_text,
            "keyword": keyword,
            "category": category,
            "subject": subject,
            "difficulty": difficulty,
            "ai_generated": ai_generated,
            "extra": extra or {},
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        logger = logging.getLogger(__name__)
        try:
            doc = self.collection.find_one({"_id": ObjectId(question_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except (InvalidId, TypeError) as exc:
            logger.warning("Invalid question_id format: %s", question_id)
            return None

    def get_questions_by_user(
        self, user_id: str, limit: int = 50, before: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"user_id": user_id}
        if before is not None:
            query["created_at"] = {"$lt": before}

        cursor = self.collection.find(query)
        docs: List[Dict[str, Any]]

        if hasattr(cursor, "limit"):
            cursor = cursor.sort("created_at", -1).limit(limit)
            docs = list(cursor)
        else:  # Fallback for test doubles returning plain lists
            docs = sorted(
                list(cursor),
                key=lambda doc: doc.get("created_at", datetime.min),
                reverse=True,
            )[:limit]
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    def get_user_best_category(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Find the category with the highest average score for a user.
        
        Returns:
            {
                "category": str,
                "avg_score": float,
                "total_attempts": int,
                "total_score": int
            }
            or None if user has no quiz history
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$category",
                "avg_score": {"$avg": "$extra.score"},
                "total_attempts": {"$sum": 1},
                "total_score": {"$sum": "$extra.score"}
            }},
            {"$sort": {"avg_score": -1}},
            {"$limit": 1},
            {"$project": {
                "category": "$_id",
                "avg_score": {"$round": ["$avg_score", 2]},
                "total_attempts": 1,
                "total_score": 1,
                "_id": 0
            }}
        ]
        results = list(self.collection.aggregate(pipeline))
        return results[0] if results else None

    def get_user_performance_timeseries(
        self, user_id: str, period: str = "30d", granularity: str = "day"
    ) -> Dict[str, Any]:
        """Get time-series performance data for charting.
        
        Args:
            user_id: User identifier
            period: Time period - "7d", "30d", or "all"
            granularity: Data point frequency - "day" or "week"
            
        Returns:
            {
                "period": str,
                "data_points": [
                    {"date": str, "avg_score": float, "attempts": int},
                    ...
                ],
                "summary": {
                    "total_attempts": int,
                    "overall_avg": float
                }
            }
        """
        from datetime import timedelta
        
        # Calculate date filter based on period
        now = datetime.now()
        match_query: Dict[str, Any] = {"user_id": user_id}
        
        if period == "7d":
            match_query["created_at"] = {"$gte": now - timedelta(days=7)}
        elif period == "30d":
            match_query["created_at"] = {"$gte": now - timedelta(days=30)}
        # "all" means no date filter
        
        # Determine date format based on granularity
        date_format = "%Y-%m-%d" if granularity == "day" else "%Y-W%V"
        
        pipeline = [
            {"$match": match_query},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": date_format,
                        "date": "$created_at"
                    }
                },
                "avg_score": {"$avg": "$extra.score"},
                "attempts": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "date": "$_id",
                "avg_score": {"$round": ["$avg_score", 2]},
                "attempts": 1,
                "_id": 0
            }}
        ]
        
        data_points = list(self.collection.aggregate(pipeline))
        
        # Calculate summary statistics
        total_attempts = sum(dp["attempts"] for dp in data_points)
        overall_avg = (
            round(sum(dp["avg_score"] * dp["attempts"] for dp in data_points) / total_attempts, 2)
            if total_attempts > 0 else 0.0
        )
        
        return {
            "period": period,
            "data_points": data_points,
            "summary": {
                "total_attempts": total_attempts,
                "overall_avg": overall_avg
            }
        }
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
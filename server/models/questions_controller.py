from datetime import datetime
from typing import Optional, Dict, Any, List

from .dbcontroller import DBController


class QuestionsController:
    """Controller for storing generated questions and related metadata."""

    def __init__(self, db_controller: DBController):
        self.db_controller = db_controller
        self.collection_name = "questions"
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            if self.db_controller.db is None:
                raise Exception(
                    "Database not connected. Call db_controller.connect() first."
                )
            self.collection = self.db_controller.get_collection(self.collection_name)
        return self.collection

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
        collection = self._get_collection()
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
        result = collection.insert_one(doc)
        return str(result.inserted_id)

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        collection = self._get_collection()
        try:
            from bson import ObjectId

            doc = collection.find_one({"_id": ObjectId(question_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception:
            return None

    def get_questions_by_user(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        docs = list(
            collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        )
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    def get_random_questions(
        self, count: int = 10, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        pipeline = []
        if category:
            pipeline.append({"$match": {"category": category}})
        pipeline.append({"$sample": {"size": count}})
        results = list(collection.aggregate(pipeline))
        for r in results:
            r["_id"] = str(r["_id"])
        return results

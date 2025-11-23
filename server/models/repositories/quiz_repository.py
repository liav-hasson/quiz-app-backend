"""Repository providing read/write helpers for quiz metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_repository import BaseRepository


class QuizRepository(BaseRepository):
    """Access to the `quiz_data` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "quiz_data")

    def import_from_json(self, json_data: Dict[str, Any]) -> bool:
        try:
            self.collection.delete_many({})
            documents = []
            for topic, subtopics in json_data.items():
                for subtopic, content in subtopics.items():
                    documents.append(
                        {
                            "topic": topic,
                            "subtopic": subtopic,
                            "keywords": content.get("keywords", []),
                            "style_modifiers": content.get("style_modifiers", []),
                            "created_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    )
            if not documents:
                return False
            self.collection.insert_many(documents)
            return True
        except Exception as exc:
            print(f"Failed to import JSON data: {exc}")
            return False

    def get_all_topics(self) -> List[str]:
        return self.collection.distinct("topic")

    def get_subtopics_by_topic(self, topic: str) -> List[str]:
        return self.collection.distinct("subtopic", {"topic": topic})

    def get_keywords_by_topic_subtopic(self, topic: str, subtopic: str) -> List[str]:
        doc = self.collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("keywords", []) if doc else []

    def get_style_modifiers_by_topic_subtopic(
        self, topic: str, subtopic: str
    ) -> List[str]:
        doc = self.collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("style_modifiers", []) if doc else []

    def get_all_keywords_by_topic(self, topic: str) -> List[str]:
        docs = self.collection.find({"topic": topic})
        keywords: List[str] = []
        for doc in docs:
            keywords.extend(doc.get("keywords", []))
        return list(set(keywords))

    def add_topic_subtopic(self, topic: str, subtopic: str, keywords: List[str]) -> str:
        if self.collection.find_one({"topic": topic, "subtopic": subtopic}):
            raise ValueError(f"Topic '{topic}' with subtopic '{subtopic}' already exists")

        now = datetime.now()
        doc = {
            "topic": topic,
            "subtopic": subtopic,
            "keywords": keywords,
            "created_at": now,
            "updated_at": now,
        }
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def add_keywords_to_subtopic(
        self, topic: str, subtopic: str, new_keywords: List[str]
    ) -> bool:
        result = self.collection.update_one(
            {"topic": topic, "subtopic": subtopic},
            {
                "$addToSet": {"keywords": {"$each": new_keywords}},
                "$set": {"updated_at": datetime.now()},
            },
        )
        return result.modified_count > 0

    def remove_keywords_from_subtopic(
        self, topic: str, subtopic: str, keywords_to_remove: List[str]
    ) -> bool:
        result = self.collection.update_one(
            {"topic": topic, "subtopic": subtopic},
            {
                "$pullAll": {"keywords": keywords_to_remove},
                "$set": {"updated_at": datetime.now()},
            },
        )
        return result.modified_count > 0

    def delete_subtopic(self, topic: str, subtopic: str) -> bool:
        result = self.collection.delete_one({"topic": topic, "subtopic": subtopic})
        return result.deleted_count > 0

    def search_keywords(self, search_term: str) -> List[Dict[str, Any]]:
        regex_pattern = {"$regex": search_term, "$options": "i"}
        results = self.collection.find({"keywords": regex_pattern})

        found_items = []
        for doc in results:
            doc["_id"] = str(doc["_id"])
            matching_keywords = [
                kw for kw in doc.get("keywords", []) if search_term.lower() in kw.lower()
            ]
            if matching_keywords:
                doc["matching_keywords"] = matching_keywords
                found_items.append(doc)
        return found_items

    def get_random_keywords(
        self, topic: Optional[str] = None, count: int = 10
    ) -> List[Dict[str, Any]]:
        pipeline = []
        if topic:
            pipeline.append({"$match": {"topic": topic}})
        pipeline.append({"$unwind": "$keywords"})
        pipeline.append({"$sample": {"size": count}})
        pipeline.append({"$project": {"topic": 1, "subtopic": 1, "keyword": "$keywords"}})

        results = list(self.collection.aggregate(pipeline))
        for result in results:
            result["_id"] = str(result["_id"])
        return results

    def export_to_json_format(self) -> Dict[str, Any]:
        docs = self.collection.find({})
        json_structure: Dict[str, Any] = {}
        for doc in docs:
            topic = doc["topic"]
            subtopic = doc["subtopic"]
            keywords = doc.get("keywords", [])
            json_structure.setdefault(topic, {})[subtopic] = {"keywords": keywords}
        return json_structure

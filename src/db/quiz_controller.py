from datetime import datetime
from typing import Dict, Any, List, Optional

from .dbcontroller import DBController


class QuizController:
    def __init__(self, db_controller: DBController):
        self.db_controller = db_controller
        self.collection_name = "quiz_data"
        self.collection = None

    def _get_collection(self):
        """Get quiz collection, ensuring connection exists"""
        if self.collection is None:
            if self.db_controller.db is None:
                raise Exception(
                    "Database not connected. Call db_controller.connect() first."
                )
            self.collection = self.db_controller.get_collection(self.collection_name)
        return self.collection

    def import_from_json(self, json_data: Dict[str, Any]) -> bool:
        collection = self._get_collection()

        try:
            collection.delete_many({})

            documents = []
            for topic, subtopics in json_data.items():
                for subtopic, content in subtopics.items():
                    doc = {
                        "topic": topic,
                        "subtopic": subtopic,
                        "keywords": content.get("keywords", []),
                        "style_modifiers": content.get("style_modifiers", []),
                        "created_at": datetime.now(),
                        "updated_at": datetime.now(),
                    }
                    documents.append(doc)

            if documents:
                result = collection.insert_many(documents)
                print(f"Successfully imported {len(result.inserted_ids)} quiz topics")
                return True
            else:
                print("No data to import")
                return False

        except Exception as e:
            print(f"Failed to import JSON data: {e}")
            return False

    def get_all_topics(self) -> List[str]:
        collection = self._get_collection()
        return collection.distinct("topic")

    def get_subtopics_by_topic(self, topic: str) -> List[str]:
        collection = self._get_collection()
        return collection.distinct("subtopic", {"topic": topic})

    def get_keywords_by_topic_subtopic(self, topic: str, subtopic: str) -> List[str]:
        collection = self._get_collection()
        doc = collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("keywords", []) if doc else []

    def get_style_modifiers_by_topic_subtopic(self, topic: str, subtopic: str) -> List[str]:
        collection = self._get_collection()
        doc = collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("style_modifiers", []) if doc else []

    def get_all_keywords_by_topic(self, topic: str) -> List[str]:
        collection = self._get_collection()
        docs = collection.find({"topic": topic})
        keywords = []
        for doc in docs:
            keywords.extend(doc.get("keywords", []))
        return list(set(keywords))

    def add_topic_subtopic(self, topic: str, subtopic: str, keywords: List[str]) -> str:
        collection = self._get_collection()

        existing = collection.find_one({"topic": topic, "subtopic": subtopic})
        if existing:
            raise ValueError(
                f"Topic '{topic}' with subtopic '{subtopic}' already exists"
            )

        doc = {
            "topic": topic,
            "subtopic": subtopic,
            "keywords": keywords,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(doc)
        return str(result.inserted_id)

    def add_keywords_to_subtopic(
        self, topic: str, subtopic: str, new_keywords: List[str]
    ) -> bool:
        collection = self._get_collection()

        result = collection.update_one(
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
        collection = self._get_collection()

        result = collection.update_one(
            {"topic": topic, "subtopic": subtopic},
            {
                "$pullAll": {"keywords": keywords_to_remove},
                "$set": {"updated_at": datetime.now()},
            },
        )

        return result.modified_count > 0

    def delete_subtopic(self, topic: str, subtopic: str) -> bool:
        collection = self._get_collection()
        result = collection.delete_one({"topic": topic, "subtopic": subtopic})
        return result.deleted_count > 0

    def search_keywords(self, search_term: str) -> List[Dict[str, Any]]:
        collection = self._get_collection()

        regex_pattern = {"$regex": search_term, "$options": "i"}

        results = collection.find({"keywords": regex_pattern})

        found_items = []
        for doc in results:
            doc["_id"] = str(doc["_id"])
            matching_keywords = [
                kw for kw in doc["keywords"] if search_term.lower() in kw.lower()
            ]
            if matching_keywords:
                doc["matching_keywords"] = matching_keywords
                found_items.append(doc)

        return found_items

    def get_random_keywords(
        self, topic: Optional[str] = None, count: int = 10
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection()

        pipeline = []

        if topic:
            pipeline.append({"$match": {"topic": topic}})

        pipeline.append({"$unwind": "$keywords"})
        pipeline.append({"$sample": {"size": count}})
        pipeline.append(
            {"$project": {"topic": 1, "subtopic": 1, "keyword": "$keywords"}}
        )

        results = list(collection.aggregate(pipeline))

        for result in results:
            result["_id"] = str(result["_id"])

        return results

    def export_to_json_format(self) -> Dict[str, Any]:
        collection = self._get_collection()

        docs = collection.find({})

        json_structure = {}

        for doc in docs:
            topic = doc["topic"]
            subtopic = doc["subtopic"]
            keywords = doc["keywords"]

            if topic not in json_structure:
                json_structure[topic] = {}

            json_structure[topic][subtopic] = {"keywords": keywords}

        return json_structure

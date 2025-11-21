import pymongo
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    import boto3
except ImportError:
    boto3 = None


def _get_mongodb_credentials_from_ssm():
    """
    Fetch MongoDB credentials from AWS SSM Parameter Store.
    Returns (username, password) tuple or (None, None) if not available.
    """
    # Skip SSM in tests
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None, None

    if not boto3:
        return None, None

    try:
        ssm = boto3.client(
            "ssm", region_name=os.environ.get("AWS_REGION", "eu-north-1")
        )
        username = ssm.get_parameter(
            Name="/quiz-app/mongodb/root-username", WithDecryption=False
        )["Parameter"]["Value"]
        password = ssm.get_parameter(
            Name="/quiz-app/mongodb/root-password", WithDecryption=True
        )["Parameter"]["Value"]
        return username, password
    except Exception as e:
        print(f"Could not fetch MongoDB credentials from SSM: {e}")
        return None, None


class DBController:
    def __init__(
        self, host=None, port=None, db_name="quizdb", username=None, password=None
    ):
        """
        Initialize MongoDB connection

        Args:
            host: MongoDB hostname (default: from env MONGODB_HOST or Kubernetes service DNS)
            port: MongoDB port (default: from env MONGODB_PORT or 27017)
            db_name: Database name (default: quizdb)
            username: MongoDB username (default: from env MONGODB_USERNAME or SSM Parameter Store)
            password: MongoDB password (default: from env MONGODB_PASSWORD or SSM Parameter Store)

        Note: In Kubernetes, use mongodb.mongodb.svc.cluster.local
              For docker-compose, use 'mongodb' (service name)
              For local development, use 'localhost'

        Credential priority:
        1. Explicitly passed username/password
        2. Environment variables (MONGODB_USERNAME, MONGODB_PASSWORD)
        3. AWS SSM Parameter Store (/quiz-app/mongodb/root-username, /quiz-app/mongodb/root-password)
        4. No authentication (fallback)
        """
        self.host = host or os.environ.get(
            "MONGODB_HOST", "mongodb.mongodb.svc.cluster.local"
        )
        self.port = port or int(os.environ.get("MONGODB_PORT", "27017"))
        self.db_name = db_name

        # Try to get credentials in priority order
        self.username = username or os.environ.get("MONGODB_USERNAME")
        self.password = password or os.environ.get("MONGODB_PASSWORD")

        # If env vars not set, try fetching from SSM Parameter Store
        if not self.username or not self.password:
            ssm_username, ssm_password = _get_mongodb_credentials_from_ssm()
            self.username = self.username or ssm_username
            self.password = self.password or ssm_password

        self.client = None
        self.db = None

    def connect(self):
        """Connect to MongoDB"""
        try:
            # Build connection string with or without authentication
            if self.username and self.password:
                # Authenticated connection - use 'admin' as authSource for root user
                connection_string = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.db_name}?authSource=admin"
                print(
                    f"Connecting to MongoDB at {self.host}:{self.port} as user '{self.username}' (authSource=admin)"
                )
            else:
                # Unauthenticated connection (for local development/testing)
                connection_string = f"mongodb://{self.host}:{self.port}/"
                print(f"Connecting to MongoDB at {self.host}:{self.port} (no auth)")

            self.client = pymongo.MongoClient(connection_string)
            self.db = self.client[self.db_name]
            # Test the connection
            self.client.admin.command("ping")
            print("Connected to MongoDB successfully")
            return True
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            return False

    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client is not None:
            self.client.close()
            print("Disconnected from MongoDB")

    def get_database(self):
        """Get the database object"""
        return self.db

    def get_collection(self, collection_name):
        """Get a specific collection"""
        if self.db is not None:
            return self.db[collection_name]
        else:
            raise Exception("Not connected to database")


class UserController:
    def __init__(self, db_controller: DBController):
        self.db_controller = db_controller
        self.collection_name = "users"
        self.collection = None

    def _get_collection(self):
        """Get users collection, ensuring connection exists"""
        if self.collection is None:
            if self.db_controller.db is None:
                raise Exception(
                    "Database not connected. Call db_controller.connect() first."
                )
            self.collection = self.db_controller.get_collection(self.collection_name)
        return self.collection

    def create_user(
        self,
        username: str,
        hashed_password: str,
        profile_picture: str = "",
        experience: int = 0,
    ) -> str:
        """
        Create a new user

        Args:
            username: Unique username
            hashed_password: Already hashed password
            profile_picture: URL or path to profile picture (optional)
            experience: User's experience points (default: 0)

        Returns:
            str: The inserted user's ID
        """
        collection = self._get_collection()

        # Check if username already exists
        if collection.find_one({"username": username}):
            raise ValueError(f"Username '{username}' already exists")

        user_doc = {
            "username": username,
            "hashed_password": hashed_password,
            "profile_picture": profile_picture,
            "experience": experience,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(user_doc)
        return str(result.inserted_id)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        collection = self._get_collection()
        user = collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])  # Convert ObjectId to string
        return user

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        collection = self._get_collection()
        try:
            from bson import ObjectId

            user = collection.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])  # Convert ObjectId to string
            return user
        except Exception:
            return None

    def update_user(self, username: str, **kwargs) -> bool:
        """
        Update user fields

        Args:
            username: Username of user to update
            **kwargs: Fields to update (hashed_password, profile_picture, experience)

        Returns:
            bool: True if update successful
        """
        collection = self._get_collection()

        # Only allow updating specific fields
        allowed_fields = ["hashed_password", "profile_picture", "experience"]
        update_doc = {}

        for field, value in kwargs.items():
            if field in allowed_fields:
                update_doc[field] = value

        if not update_doc:
            return False

        update_doc["updated_at"] = datetime.now()

        result = collection.update_one({"username": username}, {"$set": update_doc})

        return result.modified_count > 0

    def delete_user(self, username: str) -> bool:
        """Delete user by username"""
        collection = self._get_collection()
        result = collection.delete_one({"username": username})
        return result.deleted_count > 0

    def add_experience(self, username: str, points: int) -> bool:
        """Add experience points to user"""
        collection = self._get_collection()
        result = collection.update_one(
            {"username": username},
            {"$inc": {"experience": points}, "$set": {"updated_at": datetime.now()}},
        )
        return result.modified_count > 0

    def get_users_by_experience_range(
        self, min_exp: int = 0, max_exp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get users within experience range"""
        collection = self._get_collection()

        query = {"experience": {"$gte": min_exp}}
        if max_exp is not None:
            query["experience"]["$lte"] = max_exp

        users = list(collection.find(query).sort("experience", -1))

        # Convert ObjectId to string for all users
        for user in users:
            user["_id"] = str(user["_id"])

        return users

    def username_exists(self, username: str) -> bool:
        """Check if username exists"""
        collection = self._get_collection()
        return collection.find_one({"username": username}) is not None

    # --- Google OAuth helpers ---
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email (for OAuth-created users)"""
        collection = self._get_collection()
        user = collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Google `sub` id"""
        collection = self._get_collection()
        user = collection.find_one({"google_id": google_id})
        if user:
            user["_id"] = str(user["_id"])
        return user


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
        """
        Import quiz data from JSON structure to MongoDB

        Args:
            json_data: The JSON data structure (like your db.json content)

        Returns:
            bool: True if import successful
        """
        collection = self._get_collection()

        try:
            # Clear existing data
            collection.delete_many({})

            # Transform and insert data
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
        """Get all unique topics"""
        collection = self._get_collection()
        return collection.distinct("topic")

    def get_subtopics_by_topic(self, topic: str) -> List[str]:
        """Get all subtopics for a specific topic"""
        collection = self._get_collection()
        return collection.distinct("subtopic", {"topic": topic})

    def get_keywords_by_topic_subtopic(self, topic: str, subtopic: str) -> List[str]:
        """Get keywords for a specific topic and subtopic"""
        collection = self._get_collection()
        doc = collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("keywords", []) if doc else []

    def get_style_modifiers_by_topic_subtopic(
        self, topic: str, subtopic: str
    ) -> List[str]:
        """Get style modifiers for a specific topic and subtopic"""
        collection = self._get_collection()
        doc = collection.find_one({"topic": topic, "subtopic": subtopic})
        return doc.get("style_modifiers", []) if doc else []

    def get_all_keywords_by_topic(self, topic: str) -> List[str]:
        """Get all keywords for a topic (across all subtopics)"""
        collection = self._get_collection()
        docs = collection.find({"topic": topic})
        keywords = []
        for doc in docs:
            keywords.extend(doc.get("keywords", []))
        return list(set(keywords))  # Remove duplicates

    def add_topic_subtopic(self, topic: str, subtopic: str, keywords: List[str]) -> str:
        """Add a new topic/subtopic with keywords"""
        collection = self._get_collection()

        # Check if combination already exists
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
        """Add keywords to an existing topic/subtopic"""
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
        """Remove keywords from a subtopic"""
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
        """Delete a subtopic"""
        collection = self._get_collection()
        result = collection.delete_one({"topic": topic, "subtopic": subtopic})
        return result.deleted_count > 0

    def search_keywords(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for keywords containing the search term"""
        collection = self._get_collection()

        # Use regex for case-insensitive search
        regex_pattern = {"$regex": search_term, "$options": "i"}

        results = collection.find({"keywords": regex_pattern})

        found_items = []
        for doc in results:
            doc["_id"] = str(doc["_id"])
            # Filter keywords that match the search term
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
        """Get random keywords for quiz generation"""
        collection = self._get_collection()

        pipeline = []

        # Filter by topic if specified
        if topic:
            pipeline.append({"$match": {"topic": topic}})

        # Unwind keywords array
        pipeline.append({"$unwind": "$keywords"})

        # Sample random keywords
        pipeline.append({"$sample": {"size": count}})

        # Project the fields we want
        pipeline.append(
            {"$project": {"topic": 1, "subtopic": 1, "keyword": "$keywords"}}
        )

        results = list(collection.aggregate(pipeline))

        # Convert ObjectIds to strings
        for result in results:
            result["_id"] = str(result["_id"])

        return results

    def export_to_json_format(self) -> Dict[str, Any]:
        """Export MongoDB data back to original JSON format"""
        collection = self._get_collection()

        # Get all documents
        docs = collection.find({})

        # Rebuild the JSON structure
        json_structure = {}

        for doc in docs:
            topic = doc["topic"]
            subtopic = doc["subtopic"]
            keywords = doc["keywords"]

            if topic not in json_structure:
                json_structure[topic] = {}

            json_structure[topic][subtopic] = {"keywords": keywords}

        return json_structure


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


class DataMigrator:
    """Helper class to migrate data from JSON to MongoDB"""

    def __init__(self, db_controller: DBController, quiz_controller: QuizController):
        self.db_controller = db_controller
        self.quiz_controller = quiz_controller

    def migrate_from_json_file(self, json_file_path: str) -> bool:
        """Migrate data from a JSON file to MongoDB"""
        import json

        try:
            with open(json_file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)

            return self.quiz_controller.import_from_json(json_data)

        except FileNotFoundError:
            print(f"JSON file not found: {json_file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"Invalid JSON format: {e}")
            return False
        except Exception as e:
            print(f"Migration failed: {e}")
            return False

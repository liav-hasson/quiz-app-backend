from datetime import datetime
from typing import Optional, Dict, Any, List

from .dbcontroller import DBController


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
        collection = self._get_collection()
        user = collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])  # Convert ObjectId to string
        return user

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
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
        collection = self._get_collection()
        result = collection.delete_one({"username": username})
        return result.deleted_count > 0

    def add_experience(self, username: str, points: int) -> bool:
        collection = self._get_collection()
        result = collection.update_one(
            {"username": username},
            {
                "$inc": {"experience": points, "questions_count": 1},
                "$set": {"updated_at": datetime.now()},
            },
        )
        return result.modified_count > 0

    def get_users_by_experience_range(
        self, min_exp: int = 0, max_exp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
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
        collection = self._get_collection()
        return collection.find_one({"username": username}) is not None

    # --- Google OAuth helpers ---
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        collection = self._get_collection()
        user = collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        collection = self._get_collection()
        user = collection.find_one({"google_id": google_id})
        if user:
            user["_id"] = str(user["_id"])
        return user

    def create_or_update_google_user(
        self,
        google_id: str,
        email: str,
        name: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> Dict[str, Any]:
        collection = self._get_collection()

        now = datetime.now()

        # Try to find by google_id first, then by email
        user = collection.find_one({"google_id": google_id})
        if not user and email:
            user = collection.find_one({"email": email})

        if user:
            # Update existing user
            update_doc = {
                "email": email,
                "name": name,
                "profile_picture": picture,
                "google_id": google_id,
                "updated_at": now,
            }
            collection.update_one({"_id": user["_id"]}, {"$set": update_doc})
            user = collection.find_one({"_id": user["_id"]})
        else:
            # Create new user
            username = email.split("@")[0] if email else "user"
            user_doc = {
                "username": username,
                "email": email,
                "name": name,
                "profile_picture": picture,
                "google_id": google_id,
                "experience": 0,
                "questions_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            result = collection.insert_one(user_doc)
            user = collection.find_one({"_id": result.inserted_id})

        if user is None:
            raise RuntimeError("Failed to create or update user")
        user["_id"] = str(user["_id"])
        return user

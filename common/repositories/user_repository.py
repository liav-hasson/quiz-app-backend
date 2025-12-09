"""Mongo repository for user documents."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId  # type: ignore
from bson.errors import InvalidId

from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    """CRUD helpers for the `users` collection."""

    def __init__(self, db_controller) -> None:
        super().__init__(db_controller, "users")

    def create_user(
        self,
        username: str,
        hashed_password: str,
        profile_picture: str = "",
        experience: int = 0,
    ) -> str:
        if self.collection.find_one({"username": username}):
            raise ValueError(f"Username '{username}' already exists")

        now = datetime.now()
        user_doc = {
            "username": username,
            "hashed_password": hashed_password,
            "profile_picture": profile_picture,
            "experience": experience,
            "questions_count": 0,
            "streak": 0,
            "last_activity_date": None,
            "created_at": now,
            "updated_at": now,
        }
        result = self.collection.insert_one(user_doc)
        return str(result.inserted_id)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        user = self.collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])
        return user

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        logger = logging.getLogger(__name__)
        try:
            user = self.collection.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except (InvalidId, TypeError) as exc:
            logger.warning("Invalid user_id format: %s", user_id)
            return None

    def update_user(self, username: str, **kwargs) -> bool:
        allowed_fields = ["hashed_password", "profile_picture", "experience"]
        update_doc = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_doc:
            return False

        update_doc["updated_at"] = datetime.now()
        result = self.collection.update_one({"username": username}, {"$set": update_doc})
        return result.modified_count > 0

    def delete_user(self, username: str) -> bool:
        result = self.collection.delete_one({"username": username})
        return result.deleted_count > 0

    def add_experience(self, username: str, points: int) -> bool:
        result = self.collection.update_one(
            {"username": username},
            {
                "$inc": {"experience": points, "questions_count": 1},
                "$set": {"updated_at": datetime.now()},
            },
        )
        return result.modified_count > 0

    def add_bonus_xp(self, user_id: str, points: int) -> bool:
        """Add bonus XP (from daily missions, etc.) without incrementing questions_count.
        
        Args:
            user_id: User's ObjectId as string
            points: XP points to add
            
        Returns:
            bool: True if update successful
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$inc": {"experience": points},
                    "$set": {"updated_at": datetime.now()},
                },
            )
            return result.modified_count > 0
        except InvalidId:
            return False

    def update_streak(self, user_id: str, streak: int, last_activity_date: datetime) -> bool:
        """Update user's streak and last activity date.
        
        Args:
            user_id: User's ID
            streak: New streak value
            last_activity_date: Date of last activity
            
        Returns:
            bool: True if update successful
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "streak": streak,
                        "last_activity_date": last_activity_date,
                        "updated_at": datetime.now(),
                    }
                },
            )
            return result.modified_count > 0
        except (InvalidId, TypeError):
            return False

    def get_users_by_experience_range(
        self, min_exp: int = 0, max_exp: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"experience": {"$gte": min_exp}}
        if max_exp is not None:
            query["experience"]["$lte"] = max_exp

        users = list(self.collection.find(query).sort("experience", -1))
        for user in users:
            user["_id"] = str(user["_id"])
        return users

    def username_exists(self, username: str) -> bool:
        return self.collection.find_one({"username": username}) is not None

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by total experience (weighted XP).
        
        Rankings are based on total XP earned. Average score is shown as a secondary stat.
        
        Args:
            limit: Number of top users to return (default 10)
            
        Returns:
            List of users with rank, username, total_score, avg_score, attempts
        """
        import math
        
        pipeline = [
            # Only include users who have answered questions
            {"$match": {"questions_count": {"$gt": 0}}},
            # Calculate average score as secondary stat
            {"$addFields": {
                "avg_score": {
                    "$divide": ["$experience", "$questions_count"]
                }
            }},
            # Sort by total experience (XP) descending
            {"$sort": {"experience": -1}},
            # Limit to top N
            {"$limit": limit},
            # Project fields we want to return
            {"$project": {
                "_id": {"$toString": "$_id"},
                "username": 1,
                "email": 1,
                "name": 1,
                "total_score": "$experience",
                "avg_score": {"$ceil": "$avg_score"},  # Round up as secondary stat
                "attempts": "$questions_count"
            }}
        ]
        
        users = list(self.collection.aggregate(pipeline))
        
        # Add rank positions
        for idx, user in enumerate(users):
            user["rank"] = idx + 1
        
        return users

    def get_user_rank(self, username: str) -> Optional[Dict[str, Any]]:
        """Get a specific user's rank and stats based on total XP.
        
        Rankings are based on total experience (weighted XP), not average score.
        
        Returns:
            Dict with rank, username, total_score, avg_score, attempts, percentile
            or None if user not found or has no attempts
        """
        import math
        
        user = self.get_user_by_username(username)
        if not user or user.get("questions_count", 0) == 0:
            return None
        
        exp = user.get("experience", 0)
        count = user.get("questions_count", 0)
        avg_score = math.ceil(exp / count) if count > 0 else 0
        
        # Count how many users have higher total XP
        higher_count = self.collection.count_documents({
            "questions_count": {"$gt": 0},
            "experience": {"$gt": exp}
        })
        rank = higher_count + 1
        
        # Get total users with attempts for percentile
        total_users = self.collection.count_documents({"questions_count": {"$gt": 0}})
        percentile = ((total_users - rank) / total_users * 100) if total_users > 0 else 0
        
        return {
            "rank": rank,
            "username": user.get("username") or user.get("email"),
            "avg_score": avg_score,
            "total_score": exp,
            "attempts": count,
            "percentile": round(percentile, 1)
        }

    # OAuth helpers
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        # Basic email validation
        if not isinstance(email, str) or '@' not in email or len(email) < 3:
            raise ValueError("Invalid email format")
        
        user = self.collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        user = self.collection.find_one({"google_id": google_id})
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
        now = datetime.now()

        user = self.collection.find_one({"google_id": google_id})
        if not user and email:
            user = self.collection.find_one({"email": email})

        if user:
            update_doc = {
                "email": email,
                "name": name,
                "picture": picture,
                "google_id": google_id,
                "updated_at": now,
            }
            self.collection.update_one({"_id": user["_id"]}, {"$set": update_doc})
            user = self.collection.find_one({"_id": user["_id"]})
        else:
            username = email.split("@")[0] if email else "user"
            user_doc = {
                "username": username,
                "email": email,
                "name": name,
                "picture": picture,
                "google_id": google_id,
                "experience": 0,
                "questions_count": 0,
                "streak": 0,
                "last_activity_date": None,
                "created_at": now,
                "updated_at": now,
            }
            result = self.collection.insert_one(user_doc)
            user = self.collection.find_one({"_id": result.inserted_id})

        if user is None:
            raise RuntimeError("Failed to create or update user")

        user["_id"] = str(user["_id"])
        return user

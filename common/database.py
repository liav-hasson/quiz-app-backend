"""MongoDB connection utilities."""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

import pymongo
import boto3

logger = logging.getLogger(__name__)


def _get_mongodb_credentials_from_ssm() -> Tuple[Optional[str], Optional[str]]:
    """Fetch MongoDB credentials from AWS SSM Parameter Store.
    
    Falls back gracefully if AWS credentials are not available
    (e.g., in docker-compose environment with env vars).
    """

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
        logger.info("mongodb_credentials_fetched_from_ssm")
        return username, password
    except Exception as exc:  # pragma: no cover
        # Expected in docker-compose environment (uses env vars instead)
        logger.debug("ssm_credentials_unavailable using_env_vars error=%s", exc)
        return None, None


class DBController:
    """Small wrapper around a PyMongo client connection."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db_name: str = "quizdb",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.host = host or os.environ.get(
            "MONGODB_HOST", "mongodb.mongodb.svc.cluster.local"
        )
        self.port = port or int(os.environ.get("MONGODB_PORT", "27017"))
        self.db_name = db_name

        self.username = username or os.environ.get("MONGODB_USERNAME")
        self.password = password or os.environ.get("MONGODB_PASSWORD")
        if not self.username or not self.password:
            ssm_username, ssm_password = _get_mongodb_credentials_from_ssm()
            self.username = self.username or ssm_username
            self.password = self.password or ssm_password

        self.client: Optional[pymongo.MongoClient] = None
        self.db = None

    def _build_connection_string(self) -> str:
        if self.username and self.password:
            return (
                f"mongodb://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.db_name}?authSource=admin"
            )
        return f"mongodb://{self.host}:{self.port}/"

    def connect(self, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """Connect to MongoDB and verify the connection with retries.
        
        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Seconds to wait between retries
        """
        import time
        
        for attempt in range(1, max_retries + 1):
            try:
                self.client = pymongo.MongoClient(
                    self._build_connection_string(),
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000,
                    connect=False  # Lazy connection - avoid eventlet issues
                )
                self.db = self.client[self.db_name]
                self.client.admin.command("ping")
                logger.info("Connected to MongoDB successfully on attempt %d/%d", attempt, max_retries)
                return True
            except Exception as exc:  # pragma: no cover - best effort logging
                logger.warning(
                    "Failed to connect to MongoDB (attempt %d/%d): %s",
                    attempt, max_retries, exc
                )
                self.client = None
                self.db = None
                if attempt < max_retries:
                    logger.info("Retrying in %d seconds...", retry_delay)
                    time.sleep(retry_delay)
                else:
                    logger.error("Failed to connect to MongoDB after %d attempts", max_retries)
                    return False
        
        return False

    def disconnect(self) -> None:
        """Disconnect from MongoDB."""

        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("Disconnected from MongoDB")

    def get_database(self):
        """Return the active database instance."""

        return self.db

    def get_collection(self, collection_name: str):
        """Return a specific collection reference."""

        if self.db is None:
            raise RuntimeError("Not connected to database")
        return self.db[collection_name]

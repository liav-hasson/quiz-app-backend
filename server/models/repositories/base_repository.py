"""Shared repository helpers for Mongo-backed collections."""

from __future__ import annotations

from typing import Optional

from models.database import DBController


class BaseRepository:
    """Base repository providing lazy collection access."""

    collection_name: str

    def __init__(self, db_controller: DBController, collection_name: str) -> None:
        if not collection_name:
            raise ValueError("collection_name is required")
        self._db_controller = db_controller
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            db = self._db_controller.db
            if db is None:
                raise RuntimeError(
                    "Database not connected. Call DBController.connect() before using repositories."
                )
            self._collection = db[self.collection_name]
        return self._collection

    def reset_cache(self) -> None:
        """Clear cached PyMongo collection reference (used for reconnects)."""
        self._collection = None

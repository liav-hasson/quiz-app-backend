import json
import logging
from typing import Dict

from .database import DBController
from .repositories.quiz_repository import QuizRepository

logger = logging.getLogger(__name__)


class DataMigrator:
    """Helper class to migrate data from JSON to MongoDB"""

    def __init__(self, db_controller: DBController, quiz_repository: QuizRepository):
        self.db_controller = db_controller
        self.quiz_repository = quiz_repository

    def migrate_from_json_file(self, json_file_path: str) -> bool:
        try:
            with open(json_file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)

            return self.quiz_repository.import_from_json(json_data)

        except FileNotFoundError as e:
            logger.error("JSON file not found: %s", json_file_path)
            return False
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON format: %s", e)
            return False
        except Exception as e:
            logger.error("Migration failed: %s", e, exc_info=True)
            return False

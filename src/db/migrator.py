from typing import Dict

from .dbcontroller import DBController
from .quiz_controller import QuizController


class DataMigrator:
    """Helper class to migrate data from JSON to MongoDB"""

    def __init__(self, db_controller: DBController, quiz_controller: QuizController):
        self.db_controller = db_controller
        self.quiz_controller = quiz_controller

    def migrate_from_json_file(self, json_file_path: str) -> bool:
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

"""Pytest configuration and fixtures for tests."""
import sys
import os
from unittest.mock import MagicMock

# Add python and db directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'db'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

# Define test data
VALID_TOPICS = ['Containers', 'CI/CD', 'Kubernetes']
VALID_SUBTOPICS = ['Basics', 'Advanced']
VALID_KEYWORDS = ['Docker', 'Kubernetes', 'Podman']

# Create mock QuizController with smart behavior
mock_quiz_controller = MagicMock()
mock_quiz_controller.get_all_topics.return_value = VALID_TOPICS
mock_quiz_controller.get_subtopics_by_topic.side_effect = lambda t: VALID_SUBTOPICS if t in VALID_TOPICS else []
mock_quiz_controller.get_keywords_by_topic_subtopic.side_effect = lambda t, s: VALID_KEYWORDS if t in VALID_TOPICS and s in VALID_SUBTOPICS else []

# Create mock DBController
mock_db_controller = MagicMock()
mock_db_controller.connect.return_value = True
mock_db_controller.db = MagicMock()

# Patch dbcontroller module before any imports
sys.modules['dbcontroller'] = MagicMock()
sys.modules['dbcontroller'].DBController = MagicMock(return_value=mock_db_controller)
sys.modules['dbcontroller'].QuizController = MagicMock(return_value=mock_quiz_controller)

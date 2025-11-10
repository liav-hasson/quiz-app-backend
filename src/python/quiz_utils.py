import json
import os
import random

db_path = os.path.join(os.path.dirname(__file__), '..', 'db/db.json')

# Load the database once at module import
with open(db_path, encoding='utf-8') as f:
    DATABASE = json.load(f)


def get_categories():
    """Return a list of all categories."""
    return list(DATABASE.keys())


def get_subjects(category):
    """Return a list of subjects for a given category."""
    if category not in DATABASE:
        return []
    return list(DATABASE[category].keys())


def get_random_keyword(category, subject):
    """Return a random keyword for a given category and subject."""
    if category not in DATABASE or subject not in DATABASE[category]:
        return None
    
    keywords = DATABASE[category][subject].get("keywords", [])
    return random.choice(keywords) if keywords else None

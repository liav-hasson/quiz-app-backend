"""Quiz database utilities.

Functions for loading and querying the quiz question database.
"""
import json
import os
import random

db_path = os.path.join(os.path.dirname(__file__), '..', 'db/db.json')

# Load the database
with open(db_path, encoding='utf-8') as f:
    DATABASE = json.load(f)


def get_categories():
    """Return a list of all categories."""
    if isinstance(DATABASE, list):
        return [item.get('name') for item in DATABASE if 'name' in item]
    return list(DATABASE.keys())


def get_subjects(category):
    """Return a list of subjects for a given category."""
    if isinstance(DATABASE, list):
        for item in DATABASE:
            if item.get('name') == category:
                if 'subjects' in item and isinstance(item['subjects'], dict):
                    return list(item['subjects'].keys())
                if 'subjects' in item and isinstance(item['subjects'], list):
                    return [
                        subject.get('name')
                        for subject in item['subjects']
                        if 'name' in subject
                    ]
        return []
    
    if category in DATABASE:
        return list(DATABASE[category].keys())
    return []


def get_random_keyword(category, subject):
    """Return a random keyword for a given category and subject."""
    if category in DATABASE and subject in DATABASE[category]:
        keywords = DATABASE[category][subject].get("keywords", [])
        return random.choice(keywords) if keywords else None
    return None

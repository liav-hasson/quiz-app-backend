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

def debug_database_structure():
    """Debug function to print database structure."""
    print("=== DATABASE STRUCTURE DEBUG ===")
    print("Database type:", type(DATABASE))

    if isinstance(DATABASE, list):
        print("Database is a list with", len(DATABASE), "items")
        if DATABASE:
            print("\nFirst item structure:")
            print("First item:", DATABASE[0])
            print("First item type:", type(DATABASE[0]))

            # Show keys of first item if it's a dictionary
            if isinstance(DATABASE[0], dict):
                print("Keys in first item:", list(DATABASE[0].keys()))

    elif isinstance(DATABASE, dict):
        print("Database is a dictionary with keys:", list(DATABASE.keys()))
        if DATABASE:
            first_key = list(DATABASE.keys())[0]
            print("\nFirst key:", first_key)
            print("Value for first key:", DATABASE[first_key])
            print("Type of value:", type(DATABASE[first_key]))

            # If the value is a dictionary, show its keys
            if isinstance(DATABASE[first_key], dict):
                print("Keys in first value:", list(DATABASE[first_key].keys()))

    print("=" * 40)

def get_categories():
    """Return a list of all categories."""
    if isinstance(DATABASE, list):
        # If DATABASE is a list, extract category names
        return [item.get('name') for item in DATABASE if 'name' in item]
    # If DATABASE is a dictionary, return the keys
    return list(DATABASE.keys())

def get_subjects(category):
    """Return a list of subjects for a given category."""
    if isinstance(DATABASE, list):
        # Find the category in the list
        for item in DATABASE:
            if item.get('name') == category:
                if 'subjects' in item and isinstance(item['subjects'], dict):
                    return list(item['subjects'].keys())
                if 'subjects' in item and isinstance(item['subjects'], list):
                    # Handle case where subjects is a list
                    return [
                        subject.get('name')
                        for subject in item['subjects']
                        if 'name' in subject
                    ]
        return []
    # Original logic for dictionary
    if category in DATABASE:
        return list(DATABASE[category].keys())
    return []

def get_random_keyword(category, subject):
    """Return a random keyword for a given category and subject."""
    try:
        if category in DATABASE and subject in DATABASE[category]:
            keywords = DATABASE[category][subject].get("keywords", [])
            return random.choice(keywords) if keywords else None
        return None
    
    except (KeyError, IndexError, TypeError) as exc:
        print(f"Error in get_random_keyword: {exc}")
        print(f"Category: {category}, Subject: {subject}")
        return None

# Run debug only when this file is executed directly
if __name__ == '__main__':
    debug_database_structure()

    # Test the functions
    print("\n=== FUNCTION TESTS ===")

    # Test get_categories
    categories = get_categories()
    print("Categories:", categories)

    if categories:
        # Test get_subjects for first category
        subjects = get_subjects(categories[0])
        print(f"Subjects for '{categories[0]}':", subjects)

        if subjects:
            # Test get_random_keyword for first category and subject
            keyword = get_random_keyword(categories[0], subjects[0])
            print(
                f"Random keyword for '{categories[0]}' -> "
                f"'{subjects[0]}': {keyword}"
            )

    print("=" * 40)

"""Tests for user activity history recording and retrieval."""

from datetime import datetime


def _create_test_user(app, email: str = "history@example.com", name: str = "History User"):
    """Helper to create a test user using the app's user repository."""
    user_repository = app.extensions['user_repository']
    return user_repository.create_or_update_google_user(
        google_id=f"google-{email}", email=email, name=name
    )


def test_save_answer_and_history_flow(client, app_instance):
    user = _create_test_user(app_instance)

    payload = {
        "user_id": user["_id"],
        "username": user.get("username"),
        "question": "What is Docker?",
        "answer": "A container runtime",
        "difficulty": 1,
        "category": "Containers",
        "subject": "Basics",
        "keyword": "Docker",
        "score": 8,
        "evaluation": {"score": "8/10", "feedback": "Great"},
    }

    response = client.post("/api/user/answers", json=payload)
    assert response.status_code == 201
    answer_id = response.get_json()["answer_id"]
    assert answer_id

    history_response = client.get(
        f"/api/user/history?email={user['email']}&limit=5"
    )
    assert history_response.status_code == 200
    data = history_response.get_json()
    assert data["count"] == 1
    entry = data["history"][0]
    assert entry["summary"]["category"] == "Containers"
    assert entry["summary"]["score"] == 8
    assert entry["details"]["question"] == "What is Docker?"
    assert entry["details"]["answer"] == "A container runtime"
    assert entry["details"]["evaluation"]["feedback"] == "Great"
    created_at = entry["summary"]["created_at"]
    datetime.fromisoformat(created_at)

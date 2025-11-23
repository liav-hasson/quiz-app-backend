"""Tests for Flask API endpoints."""

from unittest.mock import patch


def test_health(client):
    """Health endpoint should return ok."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'dependencies' in data
    assert set(data['dependencies'].keys()) == {'database', 'ai_provider', 'oauth'}
    assert all(entry['healthy'] for entry in data['dependencies'].values())


def test_categories(client):
    """Categories endpoint should return list."""
    response = client.get('/api/categories')
    assert response.status_code == 200
    assert len(response.get_json()['categories']) > 0


def test_subjects(client):
    """Subjects endpoint should return list for valid category."""
    response = client.get('/api/subjects?category=Containers')
    assert response.status_code == 200
    assert 'subjects' in response.get_json()


def test_subjects_missing_category(client):
    """Missing category should return 400."""
    response = client.get('/api/subjects')
    assert response.status_code == 400


def test_generate_question(client):
    """Generate question should return question data."""

    with patch("routes.quiz_routes.quiz_controller") as mock_controller, patch(
        "routes.quiz_routes.generate_question"
    ) as mock_generate:
        mock_controller.get_random_keyword.return_value = "Docker"
        mock_controller.get_random_style_modifier.return_value = "friendly"
        mock_generate.return_value = "What is Docker?"

        response = client.post(
            "/api/question/generate",
            json={
                "category": "Containers",
                "subject": "Basics",
                "difficulty": 1,
            },
        )

    assert response.status_code == 200
    assert "question" in response.get_json()


def test_evaluate_answer(client):
    """Evaluate answer should return feedback."""

    with patch("routes.quiz_routes.evaluate_answer") as mock_eval:
        mock_eval.return_value = {"feedback": "Score: 8/10"}

        response = client.post(
            "/api/answer/evaluate",
            json={
                "question": "What is Docker?",
                "answer": "A container platform",
                "difficulty": 1,
            },
        )

    assert response.status_code == 200
    assert "feedback" in response.get_json()

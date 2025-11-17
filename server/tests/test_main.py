"""Tests for Flask API endpoints."""
import pytest
from unittest.mock import patch
from app import app


@pytest.fixture
def client():
    """Test client for Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    """Health endpoint should return ok."""
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


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


@patch('app.generate_question')
def test_generate_question(mock_gen, client):
    """Generate question should return question data."""
    mock_gen.return_value = "What is Docker?"
    response = client.post('/api/question/generate', json={
        'category': 'Containers',
        'subject': 'Basics',
        'difficulty': 1
    })
    assert response.status_code == 200
    assert 'question' in response.get_json()


@patch('app.evaluate_answer')
def test_evaluate_answer(mock_eval, client):
    """Evaluate answer should return feedback."""
    mock_eval.return_value = "Score: 8/10"
    response = client.post('/api/answer/evaluate', json={
        'question': 'What is Docker?',
        'answer': 'A container platform',
        'difficulty': 1
    })
    assert response.status_code == 200
    assert 'feedback' in response.get_json()

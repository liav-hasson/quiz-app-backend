"""Tests for health check endpoints."""


def test_health_check(client):
    """Health check endpoint should return healthy status."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'quiz-multiplayer'


def test_readiness_check(client):
    """Readiness check should return status even without Redis."""
    response = client.get('/api/health/ready')
    # Should return 200 (healthy or degraded, not error)
    assert response.status_code == 200
    data = response.get_json()
    assert data['service'] == 'quiz-multiplayer'
    assert 'status' in data
    assert 'redis' in data

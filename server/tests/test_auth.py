import pytest
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_oauth_callback_issues_jwt(client):
    # Mock oauth.google methods and user_controller
    fake_token = {'access_token': 'abc'}
    fake_userinfo = {'sub': 'google-sub-1', 'email': 'user@example.com', 'name': 'Test User', 'picture': 'http://example.com/pic.png'}

    with patch('app.oauth') as mock_oauth:
        mock_google = MagicMock()
        mock_google.authorize_access_token.return_value = fake_token
        mock_google.parse_id_token.return_value = fake_userinfo
        mock_oauth.google = mock_google

        # Patch user_controller to return a user dict
        with patch('app.user_controller') as mock_uc:
            mock_uc.create_or_update_google_user.return_value = {'_id': 'user-id-1', 'email': 'user@example.com', 'name': 'Test User'}

            resp = client.get('/api/auth/callback')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'token' in data
            assert 'user' in data
            assert data['user']['_id'] == 'user-id-1'

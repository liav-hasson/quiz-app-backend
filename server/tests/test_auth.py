from unittest.mock import patch


def test_google_login_issues_jwt(client):
    """POST /api/auth/google-login should return JWT payload."""

    fake_result = {
        "email": "user@example.com",
        "name": "Test User",
        "picture": "http://example.com/pic.png",
        "token": "app-jwt",
    }

    with patch("routes.auth_routes.auth_controller") as mock_controller:
        mock_controller.handle_google_token_login.return_value = (fake_result, 200)

        resp = client.post(
            "/api/auth/google-login",
            json={"credential": "fake-google-id-token"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["token"] == "app-jwt"
    assert data["email"] == "user@example.com"

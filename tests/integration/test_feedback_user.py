"""
Integration tests for the POST /api/feedback_user endpoint.

Tests JWT authentication, validation, and response format.
Uses mocked auth and database to avoid external dependencies.
"""

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_jwt_auth():
    """Override auth.verify with a mock that always succeeds."""
    from src.main import app, auth

    async def _mock_verify():
        return {"sub": "test_user", "token": "mock_token"}

    app.dependency_overrides[auth.verify] = _mock_verify
    yield app
    app.dependency_overrides.clear()


AUTH_HEADERS = {"Authorization": "Bearer mock_token"}

VALID_PAYLOAD = {"messageId": "msg_123", "feedback": "positive"}


# ---------------------------------------------------------------------------
# Authentication tests (no mock_jwt_auth -- real auth is exercised)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_feedback_requires_jwt(test_client):
    """Feedback endpoint rejects requests without JWT token."""
    response = test_client.post("/api/feedback_user", json=VALID_PAYLOAD)
    assert response.status_code in [401, 403], \
        f"Expected 401/403 without auth, got {response.status_code}"


@pytest.mark.integration
def test_feedback_rejects_invalid_jwt(test_client):
    """Feedback endpoint rejects requests with invalid JWT token."""
    response = test_client.post(
        "/api/feedback_user",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer invalid_token_12345"},
    )
    assert response.status_code in [401, 403], \
        f"Expected 401/403 with invalid token, got {response.status_code}"


# ---------------------------------------------------------------------------
# Validation tests (authenticated)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_feedback_rejects_missing_message_id(test_client, mock_jwt_auth):
    """422 when messageId is missing from request body."""
    response = test_client.post(
        "/api/feedback_user",
        json={"feedback": "positive"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert data["type"] == "error"
    assert data["code"] == "BAD_REQUEST"


@pytest.mark.integration
def test_feedback_rejects_empty_message_id(test_client, mock_jwt_auth):
    """422 when messageId is an empty string."""
    response = test_client.post(
        "/api/feedback_user",
        json={"messageId": "", "feedback": "positive"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert data["type"] == "error"
    assert data["code"] == "BAD_REQUEST"


@pytest.mark.integration
def test_feedback_rejects_invalid_feedback_value(test_client, mock_jwt_auth):
    """422 when feedback is not 'positive' or 'negative'."""
    response = test_client.post(
        "/api/feedback_user",
        json={"messageId": "msg_123", "feedback": "invalid"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert data["type"] == "error"
    assert data["code"] == "BAD_REQUEST"


# ---------------------------------------------------------------------------
# Success path tests (authenticated, mocked DB)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_feedback_set_positive(test_client, mock_jwt_auth):
    """200 with updated document when setting positive feedback."""
    mock_doc = {"_id": "msg_123", "content": "Hello", "feedback_user": "positive"}

    with patch("src.services.database.database_service.MongoDBService.update_feedback") as mock_update:
        mock_update.return_value = mock_doc

        response = test_client.post(
            "/api/feedback_user",
            json={"messageId": "msg_123", "feedback": "positive"},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_user"] == "positive"
        assert data["_id"] == "msg_123"


@pytest.mark.integration
def test_feedback_set_negative(test_client, mock_jwt_auth):
    """200 with updated document when setting negative feedback."""
    mock_doc = {"_id": "msg_456", "feedback_user": "negative"}

    with patch("src.services.database.database_service.MongoDBService.update_feedback") as mock_update:
        mock_update.return_value = mock_doc

        response = test_client.post(
            "/api/feedback_user",
            json={"messageId": "msg_456", "feedback": "negative"},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_user"] == "negative"


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_feedback_message_not_found(test_client, mock_jwt_auth):
    """404 with ErrorResponse when messageId does not exist in DB."""
    with patch("src.services.database.database_service.MongoDBService.update_feedback") as mock_update:
        mock_update.return_value = None

        response = test_client.post(
            "/api/feedback_user",
            json={"messageId": "nonexistent_id", "feedback": "positive"},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "error"
        assert data["code"] == "NOT_FOUND"
        assert "nonexistent_id" in data["message"]


@pytest.mark.integration
def test_feedback_internal_error(test_client, mock_jwt_auth):
    """500 with ErrorResponse when an unexpected exception occurs."""
    with patch("src.services.database.database_service.MongoDBService.update_feedback") as mock_update:
        mock_update.side_effect = Exception("Database connection failed")

        response = test_client.post(
            "/api/feedback_user",
            json={"messageId": "msg_123", "feedback": "positive"},
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 500
        data = response.json()
        assert data["type"] == "error"
        assert data["code"] == "INTERNAL_ERROR"

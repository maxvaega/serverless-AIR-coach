"""
Integration tests for the monitoring endpoint.

Tests JWT authentication, parameter validation, and response format.
Uses mocked auth and monitoring functions to avoid external dependencies.
"""

import pytest
from unittest.mock import patch
from fastapi.security import SecurityScopes, HTTPAuthorizationCredentials


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_jwt_auth():
    """Override auth.verify with a mock that always succeeds.

    Yields the app instance so tests can use it if needed.
    Cleans up dependency_overrides automatically after each test.
    """
    from src.main import app, auth

    async def _mock_verify(
        security_scopes: SecurityScopes,
        token: HTTPAuthorizationCredentials = None,
    ):
        return {"sub": "test_user", "token": "mock_token"}

    app.dependency_overrides[auth.verify] = _mock_verify
    yield app
    app.dependency_overrides.clear()


AUTH_HEADERS = {"Authorization": "Bearer mock_token"}


# ---------------------------------------------------------------------------
# Authentication tests (no mock_jwt_auth -- real auth is exercised)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_monitoring_requires_jwt(test_client):
    """Monitoring endpoint rejects requests without JWT token."""
    response = test_client.get("/api/monitoring")
    assert response.status_code in [401, 403], \
        f"Expected 401/403 without auth, got {response.status_code}"


@pytest.mark.integration
def test_monitoring_rejects_invalid_jwt(test_client):
    """Monitoring endpoint rejects requests with invalid JWT token."""
    response = test_client.get(
        "/api/monitoring",
        headers={"Authorization": "Bearer invalid_token_12345"}
    )
    assert response.status_code in [401, 403], \
        f"Expected 401/403 with invalid token, got {response.status_code}"


# ---------------------------------------------------------------------------
# Authenticated endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_monitoring_accepts_valid_jwt(test_client, mock_jwt_auth):
    """Monitoring endpoint accepts requests with valid JWT token."""
    with patch("src.monitoring.dashboard.get_monitoring_report") as mock_report:
        mock_report.return_value = {
            "period_hours": 720,
            "token_usage": {"total_requests": 100},
        }

        response = test_client.get("/api/monitoring?days=30", headers=AUTH_HEADERS)

        assert response.status_code == 200, \
            f"Expected 200 with valid token, got {response.status_code}: {response.text}"
        mock_report.assert_called_once_with(hours=720)


@pytest.mark.integration
def test_monitoring_days_default_value(test_client, mock_jwt_auth):
    """Monitoring endpoint uses default of 30 days when not specified."""
    with patch("src.monitoring.dashboard.get_monitoring_report") as mock_report:
        mock_report.return_value = {"period_hours": 720}

        response = test_client.get("/api/monitoring", headers=AUTH_HEADERS)

        assert response.status_code == 200
        mock_report.assert_called_once_with(hours=720)


@pytest.mark.integration
@pytest.mark.parametrize("days,expected_hours", [
    (1, 24),
    (7, 168),
    (30, 720),
    (90, 2160),
])
def test_monitoring_days_conversion(test_client, mock_jwt_auth, days, expected_hours):
    """Days parameter correctly converts to hours."""
    with patch("src.monitoring.dashboard.get_monitoring_report") as mock_report:
        mock_report.return_value = {"period_hours": expected_hours}

        response = test_client.get(
            f"/api/monitoring?days={days}",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200, f"Failed for days={days}: {response.text}"
        mock_report.assert_called_once_with(hours=expected_hours)


@pytest.mark.integration
@pytest.mark.parametrize("invalid_days", [0, -1, 91, 100])
def test_monitoring_days_validation_rejects_out_of_range(test_client, mock_jwt_auth, invalid_days):
    """Days parameter rejects values outside the 1-90 range."""
    response = test_client.get(
        f"/api/monitoring?days={invalid_days}",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422, \
        f"Expected 422 for days={invalid_days}, got {response.status_code}"


@pytest.mark.integration
def test_monitoring_response_format(test_client, mock_jwt_auth):
    """Monitoring endpoint returns expected JSON structure."""
    mock_report_data = {
        "period_hours": 720,
        "generated_at": "2025-01-15T10:30:00+00:00",
        "token_usage": {
            "total_requests": 150,
            "total_input_tokens": 27750000,
            "total_output_tokens": 300000,
        },
        "cache_analysis": {
            "caching_active": True,
            "cache_hit_rate_percent": 94.7,
        },
        "cost_analysis": {
            "period_cost_usd": 0.235,
        },
        "rate_limits": {
            "total_events": 0,
        },
        "recommendations": [
            "No issues detected.",
        ],
    }

    with patch("src.monitoring.dashboard.get_monitoring_report") as mock_report:
        mock_report.return_value = mock_report_data

        response = test_client.get("/api/monitoring?days=30", headers=AUTH_HEADERS)

        assert response.status_code == 200
        data = response.json()

        expected_keys = [
            "period_hours", "token_usage", "cache_analysis",
            "cost_analysis", "rate_limits", "recommendations",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"


@pytest.mark.integration
def test_monitoring_internal_error_handling(test_client, mock_jwt_auth):
    """Monitoring endpoint handles internal errors gracefully."""
    with patch("src.monitoring.dashboard.get_monitoring_report") as mock_report:
        mock_report.side_effect = Exception("Database connection failed")

        response = test_client.get("/api/monitoring?days=7", headers=AUTH_HEADERS)

        assert response.status_code == 500, \
            f"Expected 500 for internal error, got {response.status_code}"

        data = response.json()
        assert "detail" in data
        assert "Error generating monitoring report" in data["detail"]

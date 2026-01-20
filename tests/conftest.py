import sys
from pathlib import Path
import pytest

# Assicura che la root del progetto sia nel PYTHONPATH quando pytest cambia i path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Register custom markers for test categorization"""
    config.addinivalue_line(
        "markers",
        "unit: Unit tests (fast, mocked dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (TestClient, no manual server)"
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests (require manual server: python run.py)"
    )


# ============================================================================
# Integration Test Fixtures (TestClient-based)
# ============================================================================

@pytest.fixture(scope="session")
def test_client():
    """
    Session-scoped TestClient for integration tests.

    This fixture provides a FastAPI TestClient that makes HTTP requests
    WITHOUT starting a manual server. Tests using this fixture should be
    marked with @pytest.mark.integration.

    Usage:
        @pytest.mark.integration
        def test_endpoint(test_client):
            response = test_client.get("/api/test")
            assert response.status_code == 200
    """
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """
    Generate Auth0 token headers for authenticated requests.

    This fixture attempts to get a valid Auth0 token and returns
    properly formatted authorization headers. If token generation
    fails, the test will be skipped.

    Usage:
        @pytest.mark.integration
        def test_protected_endpoint(test_client, auth_headers):
            response = test_client.post("/api/stream_query",
                                       json=payload,
                                       headers=auth_headers)
            assert response.status_code == 200
    """
    import os

    # Try environment variable first
    env_token = os.getenv("TEST_AUTH_TOKEN", "")
    if env_token:
        return {"Authorization": f"Bearer {env_token}"}

    # Try generating token
    try:
        from src.auth0 import get_auth0_token
        token = get_auth0_token()
        if not token:
            pytest.skip("Auth0 token generation failed - no token available")
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        pytest.skip(f"Auth0 token generation failed: {str(e)}")


@pytest.fixture
def test_user_id():
    """
    Standard test user ID for integration tests.

    Returns a consistent user ID for testing purposes.
    """
    return "google-oauth2|104612087445133776110"



import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from src.history_hooks import build_rolling_window_middleware

# Mark all tests in this file as unit tests (fast, mocked)
pytestmark = [pytest.mark.unit, pytest.mark.anyio]


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


async def test_rolling_window_middleware_trims_messages(anyio_backend):
    """Test that the middleware trims messages to the last N turns."""
    middleware_instance = build_rolling_window_middleware(1)

    # Build a minimal ModelRequest mock
    request = MagicMock()
    request.messages = [HumanMessage("u1"), AIMessage("a1"), HumanMessage("u2")]

    # Track what override was called with
    overridden_request = MagicMock()
    request.override.return_value = overridden_request

    # Mock async handler
    handler = AsyncMock(return_value="response")

    # Execute via the middleware's awrap_model_call method
    result = await middleware_instance.awrap_model_call(request, handler)

    # Verify override was called with trimmed messages
    request.override.assert_called_once()
    trimmed = request.override.call_args[1]["messages"]
    assert len(trimmed) == 1
    assert isinstance(trimmed[0], HumanMessage)
    assert trimmed[0].content == "u2"

    # Verify handler was called with overridden request
    handler.assert_awaited_once_with(overridden_request)
    assert result == "response"


async def test_rolling_window_middleware_fallback_on_error(anyio_backend):
    """Test that the middleware falls back to full messages on error."""
    middleware_instance = build_rolling_window_middleware(1)

    request = MagicMock()
    request.messages = [HumanMessage("u1")]
    # Make override raise an exception to trigger fallback
    request.override.side_effect = Exception("test error")

    handler = AsyncMock(return_value="fallback_response")

    with patch("src.history_hooks.logger"):
        result = await middleware_instance.awrap_model_call(request, handler)

    # Verify handler was called with original request (fallback)
    handler.assert_awaited_once_with(request)
    assert result == "fallback_response"

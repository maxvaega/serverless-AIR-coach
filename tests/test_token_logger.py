"""
Unit tests for src/monitoring/token_logger.py
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.unit
class TestLogTokenUsage:
    """Tests for log_token_usage function."""

    @patch("src.monitoring.token_logger._save_metric")
    def test_logs_token_usage_successfully(self, mock_save):
        """Should log token usage and save to MongoDB."""
        from src.monitoring.token_logger import log_token_usage

        usage = {
            "input_tokens": 185000,
            "output_tokens": 500,
            "total_tokens": 185500,
            "cached_tokens": 150000,
        }

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = True
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata=usage,
                request_duration_ms=1200.5,
                metadata={"message_id": "msg_123"},
            )

        assert result is not None
        assert result["user_id"] == "test-user"
        assert result["model"] == "gemini-flash"
        assert result["input_tokens"] == 185000
        assert result["output_tokens"] == 500
        assert result["total_tokens"] == 185500
        assert result["cached_tokens"] == 150000
        assert result["request_duration_ms"] == 1200.5
        assert result["metadata"]["message_id"] == "msg_123"
        mock_save.assert_called_once()

    @patch("src.monitoring.token_logger._save_metric")
    def test_handles_google_ai_metadata_fields(self, mock_save):
        """Should handle Google AI API field names (prompt_token_count, etc.)."""
        from src.monitoring.token_logger import log_token_usage

        usage = {
            "prompt_token_count": 200000,
            "candidates_token_count": 300,
            "total_token_count": 200300,
            "cached_content_token_count": 180000,
        }

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = True
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata=usage,
            )

        assert result["input_tokens"] == 200000
        assert result["output_tokens"] == 300
        assert result["total_tokens"] == 200300
        assert result["cached_tokens"] == 180000

    def test_returns_none_when_disabled(self):
        """Should return None when token logging is disabled."""
        from src.monitoring.token_logger import log_token_usage

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = False
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata={"input_tokens": 100},
            )

        assert result is None

    def test_returns_none_when_no_metadata(self):
        """Should return None when usage_metadata is None."""
        from src.monitoring.token_logger import log_token_usage

        result = log_token_usage(
            user_id="test-user",
            model="gemini-flash",
            usage_metadata=None,
        )

        assert result is None

    @patch("src.monitoring.token_logger._save_metric")
    def test_handles_langchain_input_token_details_format(self, mock_save):
        """Should extract cached_tokens from input_token_details.cache_read (LangChain format)."""
        from src.monitoring.token_logger import log_token_usage

        usage = {
            "input_tokens": 185000,
            "output_tokens": 500,
            "total_tokens": 185500,
            "input_token_details": {"cache_read": 150000},
        }

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = True
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata=usage,
            )

        assert result is not None
        assert result["cached_tokens"] == 150000
        mock_save.assert_called_once()

    @patch("src.monitoring.token_logger._save_metric")
    def test_input_token_details_takes_priority(self, mock_save):
        """input_token_details.cache_read should take priority over top-level cached_tokens."""
        from src.monitoring.token_logger import log_token_usage

        usage = {
            "input_tokens": 185000,
            "output_tokens": 500,
            "total_tokens": 185500,
            "cached_tokens": 99999,
            "input_token_details": {"cache_read": 150000},
        }

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = True
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata=usage,
            )

        assert result is not None
        assert result["cached_tokens"] == 150000

    @patch("src.monitoring.token_logger._save_metric", side_effect=Exception("DB error"))
    def test_handles_save_error_gracefully(self, mock_save):
        """Should return None on save error without raising."""
        from src.monitoring.token_logger import log_token_usage

        with patch("src.env.settings") as mock_settings:
            mock_settings.ENABLE_TOKEN_LOGGING = True
            result = log_token_usage(
                user_id="test-user",
                model="gemini-flash",
                usage_metadata={"input_tokens": 100},
            )

        assert result is None


@pytest.mark.unit
class TestRequestTimer:
    """Tests for RequestTimer context manager."""

    def test_measures_duration(self):
        """Should measure duration in milliseconds."""
        from src.monitoring.token_logger import RequestTimer
        import time

        with RequestTimer() as timer:
            time.sleep(0.05)  # 50ms

        assert timer.duration_ms is not None
        assert timer.duration_ms >= 40  # Allow some tolerance
        assert timer.duration_ms < 200  # But not too much

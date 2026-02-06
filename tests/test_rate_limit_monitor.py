"""
Unit tests for src/monitoring/rate_limit_monitor.py
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.unit
class TestLogRateLimitEvent:
    """Tests for log_rate_limit_event function."""

    @patch("src.monitoring.rate_limit_monitor._save_event")
    def test_logs_rate_limit_event(self, mock_save):
        """Should log a rate limit event and save to MongoDB."""
        from src.monitoring.rate_limit_monitor import log_rate_limit_event

        result = log_rate_limit_event(
            user_id="test-user",
            model="gemini-flash",
            error_message="429 Resource Exhausted: RPM limit exceeded",
            limit_type="RPM",
        )

        assert result is not None
        assert result["user_id"] == "test-user"
        assert result["model"] == "gemini-flash"
        assert result["limit_type"] == "RPM"
        assert "429" in result["error_message"]
        mock_save.assert_called_once()

    @patch("src.monitoring.rate_limit_monitor._save_event")
    def test_auto_detects_rpm_limit(self, mock_save):
        """Should auto-detect RPM limit type from error message."""
        from src.monitoring.rate_limit_monitor import log_rate_limit_event

        result = log_rate_limit_event(
            user_id="test-user",
            model="gemini-flash",
            error_message="Quota exceeded: requests per minute",
        )

        assert result["limit_type"] == "RPM"

    @patch("src.monitoring.rate_limit_monitor._save_event")
    def test_auto_detects_tpm_limit(self, mock_save):
        """Should auto-detect TPM limit type from error message."""
        from src.monitoring.rate_limit_monitor import log_rate_limit_event

        result = log_rate_limit_event(
            user_id="test-user",
            model="gemini-flash",
            error_message="tokens per minute exceeded",
        )

        assert result["limit_type"] == "TPM"

    @patch("src.monitoring.rate_limit_monitor._save_event")
    def test_truncates_long_error_messages(self, mock_save):
        """Should truncate error messages longer than 500 chars."""
        from src.monitoring.rate_limit_monitor import log_rate_limit_event

        long_message = "x" * 1000
        result = log_rate_limit_event(
            user_id="test-user",
            model="gemini-flash",
            error_message=long_message,
        )

        assert len(result["error_message"]) <= 500

    @patch("src.monitoring.rate_limit_monitor._save_event", side_effect=Exception("DB error"))
    def test_handles_save_error_gracefully(self, mock_save):
        """Should return None on save error without raising."""
        from src.monitoring.rate_limit_monitor import log_rate_limit_event

        result = log_rate_limit_event(
            user_id="test-user",
            model="gemini-flash",
            error_message="429 error",
        )

        assert result is None


@pytest.mark.unit
class TestIsRateLimited:
    """Tests for is_rate_limited function."""

    def test_detects_429_error(self):
        from src.monitoring.rate_limit_monitor import is_rate_limited
        assert is_rate_limited(Exception("HTTP 429 Too Many Requests")) is True

    def test_detects_resource_exhausted(self):
        from src.monitoring.rate_limit_monitor import is_rate_limited
        assert is_rate_limited(Exception("RESOURCE EXHAUSTED")) is True

    def test_detects_rate_limit_text(self):
        from src.monitoring.rate_limit_monitor import is_rate_limited
        assert is_rate_limited(Exception("rate limit exceeded")) is True

    def test_ignores_other_errors(self):
        from src.monitoring.rate_limit_monitor import is_rate_limited
        assert is_rate_limited(Exception("Connection timeout")) is False

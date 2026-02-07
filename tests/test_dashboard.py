"""
Unit tests for src/monitoring/dashboard.py
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone


@pytest.mark.unit
class TestGetMonitoringReport:
    """Tests for get_monitoring_report function."""

    @patch("src.monitoring.dashboard.get_rate_limit_events")
    @patch("src.monitoring.dashboard.get_token_metrics")
    def test_generates_report_with_data(self, mock_metrics, mock_rate):
        """Should generate a complete report from metrics."""
        from src.monitoring.dashboard import get_monitoring_report

        mock_metrics.return_value = [
            {
                "user_id": "user1",
                "input_tokens": 185000,
                "output_tokens": 500,
                "total_tokens": 185500,
                "cached_tokens": 150000,
                "request_duration_ms": 1200,
                "timestamp": datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
            },
            {
                "user_id": "user1",
                "input_tokens": 185000,
                "output_tokens": 400,
                "total_tokens": 185400,
                "cached_tokens": 150000,
                "request_duration_ms": 1100,
                "timestamp": datetime(2026, 2, 5, 11, 0, tzinfo=timezone.utc),
            },
        ]
        mock_rate.return_value = []

        report = get_monitoring_report(hours=24)

        assert report["period_hours"] == 24
        assert report["token_usage"]["total_requests"] == 2
        assert report["token_usage"]["total_input_tokens"] == 370000
        assert report["token_usage"]["total_output_tokens"] == 900
        assert report["cache_analysis"]["caching_active"] is True
        assert report["cache_analysis"]["cache_hit_requests"] == 2
        assert report["cost_analysis"]["period_cost_usd"] > 0
        assert report["cost_analysis"]["cache_savings_usd"] > 0
        assert report["rate_limits"]["total_events"] == 0
        assert len(report["recommendations"]) > 0

    @patch("src.monitoring.dashboard.get_rate_limit_events")
    @patch("src.monitoring.dashboard.get_token_metrics")
    def test_generates_empty_report(self, mock_metrics, mock_rate):
        """Should handle empty metrics gracefully."""
        from src.monitoring.dashboard import get_monitoring_report

        mock_metrics.return_value = []
        mock_rate.return_value = []

        report = get_monitoring_report(hours=24)

        assert report["token_usage"]["total_requests"] == 0
        assert report["cache_analysis"]["caching_active"] is False
        assert report["cost_analysis"]["period_cost_usd"] == 0

    @patch("src.monitoring.dashboard.get_rate_limit_events")
    @patch("src.monitoring.dashboard.get_token_metrics")
    def test_recommends_caching_when_inactive(self, mock_metrics, mock_rate):
        """Should recommend caching when no cached tokens detected."""
        from src.monitoring.dashboard import get_monitoring_report

        mock_metrics.return_value = [
            {
                "user_id": "user1",
                "input_tokens": 185000,
                "output_tokens": 500,
                "total_tokens": 185500,
                "cached_tokens": 0,
                "timestamp": datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
            },
        ]
        mock_rate.return_value = []

        report = get_monitoring_report(hours=24)

        caching_recs = [r for r in report["recommendations"] if "CACHING" in r]
        assert len(caching_recs) > 0
        assert "NOT active" in caching_recs[0]

    @patch("src.monitoring.dashboard.get_rate_limit_events")
    @patch("src.monitoring.dashboard.get_token_metrics")
    def test_reports_rate_limit_events(self, mock_metrics, mock_rate):
        """Should report rate limit events in recommendations."""
        from src.monitoring.dashboard import get_monitoring_report

        mock_metrics.return_value = []
        mock_rate.return_value = [
            {
                "user_id": "user1",
                "limit_type": "RPM",
                "model": "gemini-flash",
                "error_message": "429",
                "timestamp": datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
            },
        ]

        report = get_monitoring_report(hours=24)

        assert report["rate_limits"]["total_events"] == 1
        rate_recs = [r for r in report["recommendations"] if "RATE LIMITS" in r]
        assert len(rate_recs) > 0


@pytest.mark.unit
class TestCostCalculation:
    """Tests for cost calculation logic."""

    @patch("src.monitoring.dashboard.get_rate_limit_events")
    @patch("src.monitoring.dashboard.get_token_metrics")
    def test_cache_reduces_cost(self, mock_metrics, mock_rate):
        """Cached tokens should result in lower cost than non-cached."""
        from src.monitoring.dashboard import get_monitoring_report

        mock_metrics.return_value = [
            {
                "user_id": "user1",
                "input_tokens": 200000,
                "output_tokens": 500,
                "total_tokens": 200500,
                "cached_tokens": 180000,
                "timestamp": datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
            },
        ]
        mock_rate.return_value = []

        report = get_monitoring_report(hours=24)

        costs = report["cost_analysis"]
        assert costs["period_cost_usd"] < costs["cost_without_cache_usd"]
        assert costs["cache_savings_usd"] > 0

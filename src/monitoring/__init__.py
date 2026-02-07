"""
Monitoring module for AIR Coach API
Provides cache monitoring, token logging, rate limit tracking, and dashboard.
"""

from .cache_monitor import log_cache_metrics, log_request_context, analyze_cache_effectiveness
from .token_logger import log_token_usage, get_token_metrics, RequestTimer
from .rate_limit_monitor import log_rate_limit_event, get_rate_limit_events, is_rate_limited
from .dashboard import get_monitoring_report

__all__ = [
    "log_cache_metrics",
    "log_request_context",
    "analyze_cache_effectiveness",
    "log_token_usage",
    "get_token_metrics",
    "RequestTimer",
    "log_rate_limit_event",
    "get_rate_limit_events",
    "is_rate_limited",
    "get_monitoring_report",
]

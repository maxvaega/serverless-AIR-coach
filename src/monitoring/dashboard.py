"""
Monitoring dashboard for AIR Coach API.

Aggregates token usage, cache effectiveness, and rate limit data
with automatic recommendations.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .token_logger import get_token_metrics
from .rate_limit_monitor import get_rate_limit_events

logger = logging.getLogger("uvicorn")

# Gemini Flash pricing (per 1M tokens)
PRICING = {
    "input": 0.10,
    "output": 0.40,
    "cached_input": 0.025,
}


def get_monitoring_report(hours: int = 24) -> Dict[str, Any]:
    """
    Generate a comprehensive monitoring report.

    Args:
        hours: Number of hours to look back

    Returns:
        Dict with token usage, cache stats, cost analysis, rate limits, and recommendations
    """
    metrics = get_token_metrics(hours=hours)
    rate_events = get_rate_limit_events(hours=hours)

    report = {
        "period_hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "token_usage": _aggregate_token_usage(metrics),
        "cache_analysis": _analyze_cache(metrics),
        "cost_analysis": _calculate_costs(metrics),
        "rate_limits": _summarize_rate_limits(rate_events),
        "recommendations": [],
    }

    report["recommendations"] = _generate_recommendations(report)

    return report


def _aggregate_token_usage(metrics: List[Dict]) -> Dict[str, Any]:
    """Aggregate token usage statistics."""
    if not metrics:
        return {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "avg_input_tokens": 0,
            "avg_output_tokens": 0,
            "avg_duration_ms": 0,
        }

    total_input = sum(m.get("input_tokens", 0) for m in metrics)
    total_output = sum(m.get("output_tokens", 0) for m in metrics)
    total_tokens = sum(m.get("total_tokens", 0) for m in metrics)
    durations = [m["request_duration_ms"] for m in metrics if m.get("request_duration_ms")]

    return {
        "total_requests": len(metrics),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "avg_input_tokens": total_input // len(metrics) if metrics else 0,
        "avg_output_tokens": total_output // len(metrics) if metrics else 0,
        "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
    }


def _analyze_cache(metrics: List[Dict]) -> Dict[str, Any]:
    """Analyze cache effectiveness."""
    if not metrics:
        return {
            "total_cached_tokens": 0,
            "cache_hit_requests": 0,
            "cache_hit_rate_percent": 0,
            "avg_cache_ratio_percent": 0,
            "caching_active": False,
        }

    total_cached = sum(m.get("cached_tokens", 0) for m in metrics)
    cache_hits = sum(1 for m in metrics if m.get("cached_tokens", 0) > 0)
    total_input = sum(m.get("input_tokens", 0) for m in metrics)

    cache_ratio = (total_cached / total_input * 100) if total_input > 0 else 0

    return {
        "total_cached_tokens": total_cached,
        "cache_hit_requests": cache_hits,
        "cache_hit_rate_percent": round(cache_hits / len(metrics) * 100, 1) if metrics else 0,
        "avg_cache_ratio_percent": round(cache_ratio, 1),
        "caching_active": total_cached > 0,
    }


def _calculate_costs(metrics: List[Dict]) -> Dict[str, Any]:
    """Calculate actual and projected costs."""
    if not metrics:
        return {
            "period_cost_usd": 0,
            "cost_without_cache_usd": 0,
            "cache_savings_usd": 0,
            "projected_monthly_usd": 0,
        }

    total_input = sum(m.get("input_tokens", 0) for m in metrics)
    total_output = sum(m.get("output_tokens", 0) for m in metrics)
    total_cached = sum(m.get("cached_tokens", 0) for m in metrics)
    non_cached_input = total_input - total_cached

    # Actual cost (non-cached input at full price + cached at discounted price + output)
    actual_cost = (
        (non_cached_input / 1_000_000 * PRICING["input"])
        + (total_cached / 1_000_000 * PRICING["cached_input"])
        + (total_output / 1_000_000 * PRICING["output"])
    )

    # Cost without cache (all input at full price + output)
    cost_no_cache = (
        (total_input / 1_000_000 * PRICING["input"])
        + (total_output / 1_000_000 * PRICING["output"])
    )

    # Find time span for projection
    timestamps = [m["timestamp"] for m in metrics if "timestamp" in m]
    if len(timestamps) >= 2:
        time_span_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        if time_span_hours > 0:
            monthly_projection = actual_cost / time_span_hours * 24 * 30
        else:
            monthly_projection = 0
    else:
        monthly_projection = 0

    return {
        "period_cost_usd": round(actual_cost, 4),
        "cost_without_cache_usd": round(cost_no_cache, 4),
        "cache_savings_usd": round(cost_no_cache - actual_cost, 4),
        "projected_monthly_usd": round(monthly_projection, 2),
    }


def _summarize_rate_limits(events: List[Dict]) -> Dict[str, Any]:
    """Summarize rate limit events."""
    if not events:
        return {
            "total_events": 0,
            "by_type": {},
            "affected_users": [],
        }

    by_type: Dict[str, int] = {}
    affected_users = set()
    for event in events:
        limit_type = event.get("limit_type", "unknown")
        by_type[limit_type] = by_type.get(limit_type, 0) + 1
        affected_users.add(event.get("user_id", "unknown"))

    return {
        "total_events": len(events),
        "by_type": by_type,
        "affected_users": list(affected_users),
    }


def _generate_recommendations(report: Dict) -> List[str]:
    """Generate actionable recommendations based on the report data."""
    recs = []

    cache = report["cache_analysis"]
    costs = report["cost_analysis"]
    rate = report["rate_limits"]
    usage = report["token_usage"]

    # Cache recommendations
    if not cache["caching_active"]:
        recs.append(
            "CACHING: Implicit caching is NOT active. "
            "Consider enabling explicit caching to reduce costs by up to 75%."
        )
    elif cache["avg_cache_ratio_percent"] < 30:
        recs.append(
            f"CACHING: Cache ratio is low ({cache['avg_cache_ratio_percent']:.1f}%). "
            "Consider explicit caching for the static system prompt."
        )

    # Cost recommendations
    if costs["projected_monthly_usd"] > 500:
        recs.append(
            f"COSTS: Projected monthly cost is ${costs['projected_monthly_usd']:.2f}. "
            "Consider migrating to Vertex AI for built-in monitoring and budget alerts."
        )

    # Rate limit recommendations
    if rate["total_events"] > 0:
        recs.append(
            f"RATE LIMITS: {rate['total_events']} rate limit events detected. "
            f"Types: {rate['by_type']}. Consider implementing request throttling."
        )

    # Token usage recommendations
    if usage["avg_input_tokens"] > 200_000:
        recs.append(
            f"CONTEXT SIZE: Average input is {usage['avg_input_tokens']:,} tokens. "
            "Consider reducing static context or implementing selective document loading."
        )

    if not recs:
        recs.append("No issues detected. System is operating normally.")

    return recs

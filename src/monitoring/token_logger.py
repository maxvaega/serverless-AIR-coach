"""
Token usage logger for AIR Coach API.

Captures and persists token usage metrics from LLM responses to MongoDB.
Enabled via ENABLE_TOKEN_LOGGING env var (default: true).
"""
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("uvicorn")

# MongoDB database name for token metrics
TOKEN_METRICS_DB = "Token_metrics"


def log_token_usage(
    user_id: str,
    model: str,
    usage_metadata: Optional[Dict[str, Any]],
    request_duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Log token usage metrics to MongoDB.

    Args:
        user_id: User identifier
        model: Model name used for the request
        usage_metadata: Token usage data from the LLM response
        request_duration_ms: Request duration in milliseconds
        metadata: Additional metadata (e.g., thread_id, message_id)

    Returns:
        The saved metric document, or None if logging is disabled/failed
    """
    from ..env import settings

    if not getattr(settings, "ENABLE_TOKEN_LOGGING", True):
        return None

    if not usage_metadata:
        logger.debug("TOKEN_LOGGER - No usage_metadata provided, skipping")
        return None

    try:
        # Extract token counts from usage_metadata
        input_tokens = (
            usage_metadata.get("input_tokens")
            or usage_metadata.get("prompt_token_count")
            or 0
        )
        output_tokens = (
            usage_metadata.get("output_tokens")
            or usage_metadata.get("candidates_token_count")
            or 0
        )
        total_tokens = (
            usage_metadata.get("total_tokens")
            or usage_metadata.get("total_token_count")
            or (input_tokens + output_tokens)
        )
        cached_tokens = (
            usage_metadata.get("cached_tokens")
            or usage_metadata.get("cached_content_token_count")
            or 0
        )

        metric = {
            "user_id": user_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "request_duration_ms": request_duration_ms,
            "timestamp": datetime.now(timezone.utc),
            "metadata": metadata or {},
        }

        # Persist to MongoDB
        _save_metric(metric)

        logger.info(
            f"TOKEN_LOGGER - User: {user_id}, "
            f"Input: {input_tokens}, Output: {output_tokens}, "
            f"Cached: {cached_tokens}, Duration: {request_duration_ms:.0f}ms"
            if request_duration_ms
            else f"TOKEN_LOGGER - User: {user_id}, "
            f"Input: {input_tokens}, Output: {output_tokens}, "
            f"Cached: {cached_tokens}"
        )

        return metric

    except Exception as e:
        logger.error(f"TOKEN_LOGGER - Error logging token usage: {e}")
        return None


def _save_metric(metric: Dict[str, Any]) -> None:
    """Save a metric document to MongoDB."""
    from ..env import COLLECTION_NAME
    from ..database import get_collection

    collection = get_collection(TOKEN_METRICS_DB, COLLECTION_NAME)
    collection.insert_one(metric)


def get_token_metrics(
    hours: int = 24,
    user_id: Optional[str] = None,
) -> list:
    """
    Retrieve token metrics from MongoDB.

    Args:
        hours: Number of hours to look back
        user_id: Optional filter by user

    Returns:
        List of metric documents
    """
    from ..env import COLLECTION_NAME
    from ..database import get_collection

    collection = get_collection(TOKEN_METRICS_DB, COLLECTION_NAME)

    since = datetime.now(timezone.utc).replace(
        hour=datetime.now(timezone.utc).hour - hours if hours < 24 else 0
    )
    # More robust time calculation
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query: Dict[str, Any] = {"timestamp": {"$gte": since}}
    if user_id:
        query["user_id"] = user_id

    return list(collection.find(query).sort("timestamp", -1))


class RequestTimer:
    """Context manager to time request duration."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        if self.start_time:
            self.duration_ms = (time.time() - self.start_time) * 1000

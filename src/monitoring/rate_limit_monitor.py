"""
Rate limit monitor for AIR Coach API.

Captures and persists rate limit (HTTP 429) events to MongoDB.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uvicorn")

# MongoDB collection name for rate limit events
RATE_LIMIT_COLLECTION = "rate_limit_events"


def log_rate_limit_event(
    user_id: str,
    model: str,
    error_message: str,
    limit_type: str = "unknown",
) -> Optional[Dict[str, Any]]:
    """
    Log a rate limit event to MongoDB.

    Args:
        user_id: User identifier
        model: Model that triggered the rate limit
        error_message: Error message from the 429 response
        limit_type: Type of limit hit (e.g., "RPM", "TPM", "RPD")

    Returns:
        The saved event document, or None if failed
    """
    try:
        # Try to detect limit type from error message
        if limit_type == "unknown":
            limit_type = _detect_limit_type(error_message)

        event = {
            "user_id": user_id,
            "limit_type": limit_type,
            "model": model,
            "error_message": str(error_message)[:500],  # Truncate long messages
            "timestamp": datetime.now(timezone.utc),
        }

        _save_event(event)

        logger.warning(
            f"RATE_LIMIT - User: {user_id}, Type: {limit_type}, "
            f"Model: {model}, Error: {str(error_message)[:200]}"
        )

        return event

    except Exception as e:
        logger.error(f"RATE_LIMIT - Error logging rate limit event: {e}")
        return None


def _detect_limit_type(error_message: str) -> str:
    """Detect the type of rate limit from the error message."""
    msg = str(error_message).lower()
    if "rpm" in msg or "requests per minute" in msg:
        return "RPM"
    elif "tpm" in msg or "tokens per minute" in msg:
        return "TPM"
    elif "rpd" in msg or "requests per day" in msg:
        return "RPD"
    elif "quota" in msg:
        return "QUOTA"
    return "unknown"


def _save_event(event: Dict[str, Any]) -> None:
    """Save a rate limit event to MongoDB."""
    from .token_logger import TOKEN_METRICS_DB
    from ..database import get_collection

    collection = get_collection(TOKEN_METRICS_DB, RATE_LIMIT_COLLECTION)
    collection.insert_one(event)


def get_rate_limit_events(
    hours: int = 24,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve rate limit events from MongoDB.

    Args:
        hours: Number of hours to look back
        user_id: Optional filter by user

    Returns:
        List of rate limit event documents
    """
    from .token_logger import TOKEN_METRICS_DB
    from ..database import get_collection

    collection = get_collection(TOKEN_METRICS_DB, RATE_LIMIT_COLLECTION)

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query: Dict[str, Any] = {"timestamp": {"$gte": since}}
    if user_id:
        query["user_id"] = user_id

    return list(collection.find(query).sort("timestamp", -1))


def is_rate_limited(error: Exception) -> bool:
    """
    Check if an exception is a rate limit error (HTTP 429).

    Args:
        error: The exception to check

    Returns:
        True if this is a rate limit error
    """
    error_str = str(error).lower()
    return "429" in error_str or "resource exhausted" in error_str or "rate limit" in error_str

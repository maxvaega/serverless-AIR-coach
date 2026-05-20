import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger("uvicorn")


def _extract_cached_tokens(usage: Any) -> int:
    """Estrae i token cached da usage_metadata di LangChain ChatOpenAI.

    OpenRouter forwarda lo schema OpenAI-compat: ``usage.prompt_tokens_details.cached_tokens``.
    LangChain lo normalizza in ``usage_metadata.input_token_details.cache_read``.
    """
    if isinstance(usage, dict):
        details = usage.get("input_token_details") or {}
        if isinstance(details, dict):
            value = details.get("cache_read")
            if value:
                return value
        return usage.get("cached_tokens", 0) or 0

    details = getattr(usage, "input_token_details", None)
    if isinstance(details, dict):
        value = details.get("cache_read")
        if value:
            return value
    return getattr(usage, "cached_tokens", 0) or 0


def _extract_total_tokens(usage: Any) -> int:
    if isinstance(usage, dict):
        return usage.get("total_tokens", 0) or 0
    return getattr(usage, "total_tokens", 0) or 0


def log_cache_metrics(response: Any) -> Dict[str, Any]:
    """Analizza e logga le metriche di caching dalla response LLM.

    Compatibile con LangChain ``ChatOpenAI`` (OpenRouter/DeepSeek): legge
    ``usage_metadata.input_token_details.cache_read`` o, in fallback,
    ``response_metadata.usage.cached_tokens``.
    """
    metrics = {
        "cached_tokens": 0,
        "total_tokens": 0,
        "cache_ratio": 0.0,
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            cached_tokens = _extract_cached_tokens(usage)
            total_tokens = _extract_total_tokens(usage)

            metrics["cached_tokens"] = cached_tokens
            metrics["total_tokens"] = total_tokens

            if total_tokens > 0:
                cache_ratio = cached_tokens / total_tokens
                metrics["cache_ratio"] = cache_ratio
                logger.info(
                    f"CACHE_METRICS - Hit ratio: {cache_ratio:.2%}, "
                    f"Cached tokens: {cached_tokens}, Total tokens: {total_tokens}"
                )
                if cached_tokens > 0:
                    savings_percent = cache_ratio * 100
                    logger.info(f"CACHE_SAVINGS - Token savings: {savings_percent:.1f}%")
            else:
                logger.debug("CACHE_METRICS - No token count available in response")

        elif hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            if 'usage' in metadata:
                usage = metadata['usage']
                total_tokens = usage.get('total_tokens', 0)
                cached_tokens = (
                    usage.get('cached_tokens')
                    or (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
                    or 0
                )

                metrics["cached_tokens"] = cached_tokens
                metrics["total_tokens"] = total_tokens

                if total_tokens > 0:
                    cache_ratio = cached_tokens / total_tokens
                    metrics["cache_ratio"] = cache_ratio
                    logger.info(f"CACHE_METRICS - Hit ratio: {cache_ratio:.2%}")

        else:
            logger.debug("CACHE_METRICS - No usage metadata found in response")

    except Exception as e:
        logger.error(f"CACHE_METRICS - Error extracting cache metrics: {e}")

    return metrics


def log_request_context(user_id: str, model: str) -> None:
    """Logga il contesto della richiesta (user + model) per debug cache."""
    try:
        logger.info(f"CACHE_CONTEXT - User: {user_id}, Model: {model}")
    except Exception as e:
        logger.error(f"CACHE_CONTEXT - Error logging request context: {e}")


def analyze_cache_effectiveness(metrics_history: list) -> Dict[str, Any]:
    """
    Analizza l'efficacia del caching su un set di metriche storiche.

    Args:
        metrics_history: Lista di metriche cache

    Returns:
        Analisi aggregata dell'efficacia del cache
    """
    if not metrics_history:
        return {"error": "No metrics history provided"}

    try:
        total_requests = len(metrics_history)
        cache_hits = sum(1 for m in metrics_history if m.get("cached_tokens", 0) > 0)

        total_tokens_sum = sum(m.get("total_tokens", 0) for m in metrics_history)
        cached_tokens_sum = sum(m.get("cached_tokens", 0) for m in metrics_history)

        hit_rate = (cache_hits / total_requests) * 100 if total_requests > 0 else 0
        overall_cache_ratio = (cached_tokens_sum / total_tokens_sum) * 100 if total_tokens_sum > 0 else 0

        analysis = {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "hit_rate_percent": hit_rate,
            "overall_cache_ratio_percent": overall_cache_ratio,
            "total_tokens": total_tokens_sum,
            "cached_tokens": cached_tokens_sum,
            "tokens_saved": cached_tokens_sum
        }

        logger.info(
            f"CACHE_ANALYSIS - Requests: {total_requests}, "
            f"Hit rate: {hit_rate:.1f}%, "
            f"Token savings: {overall_cache_ratio:.1f}%"
        )

        return analysis

    except Exception as e:
        logger.error(f"CACHE_ANALYSIS - Error analyzing cache effectiveness: {e}")
        return {"error": str(e)}
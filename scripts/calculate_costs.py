"""
Cost calculator script for AIR Coach API.

Queries token_metrics in MongoDB and calculates actual costs,
cache savings, and monthly projections.

Usage:
    python scripts/calculate_costs.py
    python scripts/calculate_costs.py --hours 168  # Last 7 days
    python scripts/calculate_costs.py --user google-oauth2|12345
"""
import argparse
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Gemini Flash pricing (per 1M tokens)
PRICING = {
    "input": 0.10,
    "output": 0.40,
    "cached_input": 0.025,
}


def main():
    parser = argparse.ArgumentParser(description="Calculate AIR Coach API costs")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back (default: 24)")
    parser.add_argument("--user", type=str, default=None, help="Filter by user ID")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(Path(PROJECT_ROOT) / ".env")

    from src.monitoring.token_logger import get_token_metrics

    print(f"Fetching token metrics for the last {args.hours} hours...")
    if args.user:
        print(f"Filtering by user: {args.user}")

    metrics = get_token_metrics(hours=args.hours, user_id=args.user)

    if not metrics:
        print("No token metrics found for the specified period.")
        sys.exit(0)

    # Aggregate
    total_input = sum(m.get("input_tokens", 0) for m in metrics)
    total_output = sum(m.get("output_tokens", 0) for m in metrics)
    total_cached = sum(m.get("cached_tokens", 0) for m in metrics)
    total_requests = len(metrics)
    non_cached_input = total_input - total_cached

    # Calculate costs
    actual_cost = (
        (non_cached_input / 1_000_000 * PRICING["input"])
        + (total_cached / 1_000_000 * PRICING["cached_input"])
        + (total_output / 1_000_000 * PRICING["output"])
    )
    cost_no_cache = (
        (total_input / 1_000_000 * PRICING["input"])
        + (total_output / 1_000_000 * PRICING["output"])
    )
    cache_savings = cost_no_cache - actual_cost

    # Duration stats
    durations = [m["request_duration_ms"] for m in metrics if m.get("request_duration_ms")]

    print(f"\n{'='*60}")
    print(f"  AIR Coach Cost Report — Last {args.hours} hours")
    print(f"{'='*60}")

    print(f"\n--- Token Usage ---")
    print(f"  Total requests:       {total_requests:>10,}")
    print(f"  Total input tokens:   {total_input:>10,}")
    print(f"  Total output tokens:  {total_output:>10,}")
    print(f"  Total cached tokens:  {total_cached:>10,}")
    print(f"  Avg input/request:    {total_input // total_requests:>10,}")
    print(f"  Avg output/request:   {total_output // total_requests:>10,}")

    if durations:
        avg_duration = sum(durations) / len(durations)
        print(f"\n--- Latency ---")
        print(f"  Avg duration:         {avg_duration:>10.0f} ms")
        print(f"  Min duration:         {min(durations):>10.0f} ms")
        print(f"  Max duration:         {max(durations):>10.0f} ms")

    print(f"\n--- Cache Analysis ---")
    cache_hits = sum(1 for m in metrics if m.get("cached_tokens", 0) > 0)
    cache_hit_rate = cache_hits / total_requests * 100
    cache_ratio = total_cached / total_input * 100 if total_input > 0 else 0
    print(f"  Cache hit requests:   {cache_hits:>10,} ({cache_hit_rate:.1f}%)")
    print(f"  Cache token ratio:    {cache_ratio:>9.1f}%")
    print(f"  Caching active:       {'YES' if total_cached > 0 else 'NO':>10}")

    print(f"\n--- Costs (Gemini Flash) ---")
    print(f"  Period cost:          ${actual_cost:>9.4f}")
    print(f"  Cost without cache:   ${cost_no_cache:>9.4f}")
    print(f"  Cache savings:        ${cache_savings:>9.4f}")

    # Monthly projections
    timestamps = [m["timestamp"] for m in metrics if "timestamp" in m]
    if len(timestamps) >= 2:
        time_span_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        if time_span_hours > 0:
            monthly = actual_cost / time_span_hours * 24 * 30
            monthly_no_cache = cost_no_cache / time_span_hours * 24 * 30
            print(f"\n--- Monthly Projection ---")
            print(f"  Projected (actual):   ${monthly:>9.2f}")
            print(f"  Projected (no cache): ${monthly_no_cache:>9.2f}")
            print(f"  Projected savings:    ${monthly_no_cache - monthly:>9.2f}")

    # Unique users
    users = set(m.get("user_id", "unknown") for m in metrics)
    print(f"\n--- Users ---")
    print(f"  Unique users:         {len(users):>10,}")
    for user in sorted(users):
        user_count = sum(1 for m in metrics if m.get("user_id") == user)
        print(f"    {user}: {user_count} requests")

    print()


if __name__ == "__main__":
    main()

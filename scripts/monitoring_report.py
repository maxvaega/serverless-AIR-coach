"""
Monitoring report script for AIR Coach API.

Generates a full monitoring report combining all metrics
with actionable recommendations.

Usage:
    python scripts/monitoring_report.py
    python scripts/monitoring_report.py --hours 168  # Last 7 days
    python scripts/monitoring_report.py --json        # JSON output
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="AIR Coach monitoring report")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back (default: 24)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(Path(PROJECT_ROOT) / ".env")

    from src.monitoring.dashboard import get_monitoring_report

    report = get_monitoring_report(hours=args.hours)

    if args.json_output:
        # Serialize datetime objects
        print(json.dumps(report, indent=2, default=str))
        return

    # Pretty print
    print(f"{'='*60}")
    print(f"  AIR Coach Monitoring Report")
    print(f"  Period: last {report['period_hours']} hours")
    print(f"  Generated: {report['generated_at']}")
    print(f"{'='*60}")

    # Token Usage
    usage = report["token_usage"]
    print(f"\n--- Token Usage ---")
    print(f"  Total requests:       {usage['total_requests']:>10,}")
    print(f"  Total input tokens:   {usage['total_input_tokens']:>10,}")
    print(f"  Total output tokens:  {usage['total_output_tokens']:>10,}")
    print(f"  Avg input/request:    {usage['avg_input_tokens']:>10,}")
    print(f"  Avg output/request:   {usage['avg_output_tokens']:>10,}")
    print(f"  Avg duration:         {usage['avg_duration_ms']:>10.1f} ms")

    # Cache Analysis
    cache = report["cache_analysis"]
    print(f"\n--- Cache Analysis ---")
    print(f"  Caching active:       {'YES' if cache['caching_active'] else 'NO':>10}")
    print(f"  Cache hit requests:   {cache['cache_hit_requests']:>10,}")
    print(f"  Cache hit rate:       {cache['cache_hit_rate_percent']:>9.1f}%")
    print(f"  Avg cache ratio:      {cache['avg_cache_ratio_percent']:>9.1f}%")
    print(f"  Total cached tokens:  {cache['total_cached_tokens']:>10,}")

    # Costs
    costs = report["cost_analysis"]
    print(f"\n--- Cost Analysis ---")
    print(f"  Period cost:          ${costs['period_cost_usd']:>9.4f}")
    print(f"  Cost without cache:   ${costs['cost_without_cache_usd']:>9.4f}")
    print(f"  Cache savings:        ${costs['cache_savings_usd']:>9.4f}")
    print(f"  Monthly projection:   ${costs['projected_monthly_usd']:>9.2f}")

    # Rate Limits
    rate = report["rate_limits"]
    print(f"\n--- Rate Limits ---")
    print(f"  Total events:         {rate['total_events']:>10,}")
    if rate["by_type"]:
        for lt, count in rate["by_type"].items():
            print(f"    {lt}: {count}")
    if rate["affected_users"]:
        print(f"  Affected users:       {len(rate['affected_users'])}")

    # Recommendations
    print(f"\n--- Recommendations ---")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"  {i}. {rec}")

    print()


if __name__ == "__main__":
    main()

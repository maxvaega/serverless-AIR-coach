"""
Token counter script for AIR Coach knowledge base documents.

Counts real tokens using Google Generative AI SDK for each document
and reports totals with cost estimates.

Usage:
    # From S3 (default)
    python scripts/count_tokens.py

    # From local directory
    python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/

    # With cache probe
    python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --probe-cache
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def count_tokens_for_text(model, text: str) -> int:
    """Count tokens for a text string using Google SDK."""
    result = model.count_tokens(text)
    return result.total_tokens


def load_local_docs(directory: str) -> dict[str, str]:
    """Load .md files from a local directory."""
    docs = {}
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Error: directory '{directory}' does not exist")
        sys.exit(1)

    for md_file in sorted(dir_path.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        docs[md_file.name] = content

    return docs


def load_s3_docs() -> dict[str, str]:
    """Load .md files from S3 bucket."""
    from src.env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME
    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    docs = {}
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key.endswith(".md"):
            body = s3.get_object(Bucket=BUCKET_NAME, Key=key)["Body"].read()
            docs[key] = body.decode("utf-8")

    return docs


def probe_cache_status(model, combined_text: str):
    """
    Probe cache status by sending a minimal request and checking
    cached_content_token_count in the response.
    """
    import google.generativeai as genai

    print("\n--- Cache Probe ---")
    try:
        response = model.generate_content(
            f"{combined_text}\n\nRispondi solo: OK",
            generation_config={"max_output_tokens": 5},
        )

        if hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
            cached = getattr(usage, "cached_content_token_count", 0) or 0
            total_input = getattr(usage, "prompt_token_count", 0) or 0
            output = getattr(usage, "candidates_token_count", 0) or 0

            print(f"  Input tokens:    {total_input:>10,}")
            print(f"  Cached tokens:   {cached:>10,}")
            print(f"  Output tokens:   {output:>10,}")
            if total_input > 0:
                ratio = cached / total_input * 100
                print(f"  Cache ratio:     {ratio:>9.1f}%")
            if cached > 0:
                print("  -> Implicit caching is ACTIVE")
            else:
                print("  -> No caching detected (normal for first request or small context)")
        else:
            print("  No usage_metadata in response")
    except Exception as e:
        print(f"  Cache probe failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Count tokens in AIR Coach documents")
    parser.add_argument(
        "--local",
        type=str,
        help="Path to local docs directory (default: load from S3)",
    )
    parser.add_argument(
        "--probe-cache",
        action="store_true",
        help="Probe cache status with a test request",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: from FORCED_MODEL env var)",
    )
    args = parser.parse_args()

    # Load API key
    from dotenv import load_dotenv
    load_dotenv(Path(PROJECT_ROOT) / ".env")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not set")
        sys.exit(1)

    import google.generativeai as genai
    genai.configure(api_key=api_key)

    model_name = args.model or os.getenv("FORCED_MODEL", "models/gemini-2.0-flash")
    # Strip "models/" prefix for GenerativeModel if present
    if model_name.startswith("models/"):
        model_name = model_name[len("models/"):]

    model = genai.GenerativeModel(model_name)
    print(f"Using model: {model_name}")

    # Load documents
    if args.local:
        print(f"Loading docs from local directory: {args.local}")
        docs = load_local_docs(args.local)
    else:
        print("Loading docs from S3...")
        docs = load_s3_docs()

    if not docs:
        print("No documents found!")
        sys.exit(1)

    # Count tokens per document
    print(f"\nFound {len(docs)} documents\n")
    print(f"{'Document':<50} {'Bytes':>10} {'Tokens':>10} {'%':>7}")
    print("-" * 80)

    total_bytes = 0
    total_tokens = 0
    doc_data = []

    for name, content in sorted(docs.items()):
        byte_count = len(content.encode("utf-8"))
        token_count = count_tokens_for_text(model, content)
        total_bytes += byte_count
        total_tokens += token_count
        doc_data.append((name, byte_count, token_count))

    for name, byte_count, token_count in doc_data:
        pct = (token_count / total_tokens * 100) if total_tokens > 0 else 0
        print(f"{name:<50} {byte_count:>10,} {token_count:>10,} {pct:>6.1f}%")

    print("-" * 80)
    print(f"{'TOTAL':<50} {total_bytes:>10,} {total_tokens:>10,} {'100.0%':>7}")

    # Cost estimates (Gemini Flash pricing)
    print("\n--- Cost Estimates (Gemini Flash) ---")
    input_cost_per_1m = 0.10  # $0.10 per 1M input tokens
    cached_cost_per_1m = 0.025  # $0.025 per 1M cached input tokens

    cost_no_cache = total_tokens / 1_000_000 * input_cost_per_1m
    cost_cached = total_tokens / 1_000_000 * cached_cost_per_1m

    print(f"  Context tokens:          {total_tokens:>10,}")
    print(f"  Cost per request (no cache):  ${cost_no_cache:.6f}")
    print(f"  Cost per request (cached):    ${cost_cached:.6f}")
    print(f"  Savings with cache:           {(1 - cached_cost_per_1m/input_cost_per_1m)*100:.0f}%")

    # Monthly projections
    for requests_per_day in [50, 100, 500]:
        monthly_no_cache = cost_no_cache * requests_per_day * 30
        monthly_cached = cost_cached * requests_per_day * 30
        print(f"\n  At {requests_per_day} requests/day:")
        print(f"    Monthly (no cache): ${monthly_no_cache:>8.2f}")
        print(f"    Monthly (cached):   ${monthly_cached:>8.2f}")
        print(f"    Monthly savings:    ${monthly_no_cache - monthly_cached:>8.2f}")

    # Cache probe
    if args.probe_cache:
        combined = "\n\n".join(content for _, content in sorted(docs.items()))
        probe_cache_status(model, combined)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
API Monitor Script
Monitors the AIR Coach API health endpoint continuously.
"""

import requests
import time
import json
from datetime import datetime
import sys


def get_timestamp():
    """Get current timestamp formatted"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def test_api():
    """
    Test the API endpoint and return success status with details
    Returns tuple: (success: bool, message: str, response_time_ms: int)
    """
    url = "https://air-coach.com/api/test"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImFPZjE3SXVqRWt4UGI1d2NXdkVZUiJ9.eyJpc3MiOiJodHRwczovL2Rldi1obGR5Z2Zrc2lxYjZyZjNkLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJNUlNqZXdLbUwxNWJWR1FvQldKbEVGVVRLNTdseWt2akBjbGllbnRzIiwiYXVkIjoiaHR0cHM6Ly9kZXYtaGxkeWdma3NpcWI2cmYzZC51cy5hdXRoMC5jb20vYXBpL3YyLyIsImlhdCI6MTc1ODg5MzYwNSwiZXhwIjoxNzU4OTc5NjA0LCJzY29wZSI6InJlYWQ6dXNlcnMiLCJndHkiOiJjbGllbnQtY3JlZGVudGlhbHMiLCJhenAiOiJNUlNqZXdLbUwxNWJWR1FvQldKbEVGVVRLNTdseWt2aiJ9.gXGcW0cwDjHtto6NkbK78E309O8_YbewtWYTEMlbKfMRVof4z3AQuoejyroGu2na-nSjJW-m4CA2OrZrBC_DgPONqiaaUn2cVjPZYGSzxflKYnbIPFbR5CuFbQK-Fxefz2lwwEbmnaGOfLa8kd0SOZ4xs9dqfse2vzHEGlsrHQEBrlfP3UuUw_pnNzsh-tDYuVE1ZARmDWJvkpYDHdGGnSP1zlExusZkSLBHiWI7xr5NO1vVoFR5AS6uuUDPVjCJAX-leYDuR-gNVTwKKo7L-rmG0cl-EBUYBu6zo9T6RdCNdqMOLf8VLpN0DmzXhbuzgldoROGKKUcKomXutGCkpA'
    }

    data = {
        "message": "Ciao come stai?",
        "userid": "google-oauth2|104612087445133776110"
    }

    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, json=data, timeout=30)
        response_time_ms = int((time.time() - start_time) * 1000)

        # Check status code
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text}", response_time_ms

        # Check if response is valid JSON
        try:
            json_data = response.json()
        except json.JSONDecodeError:
            return False, f"Invalid JSON response: {response.text}", response_time_ms

        # Check expected content
        expected_message = "API is running successfully!"
        if not isinstance(json_data, dict) or json_data.get("message") != expected_message:
            return False, f"Unexpected response content: {json_data}", response_time_ms

        return True, "API working correctly", response_time_ms

    except requests.exceptions.Timeout:
        return False, "Request timeout (>30 seconds)", 30000

    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {str(e)}", 0

    except requests.exceptions.SSLError as e:
        return False, f"SSL error: {str(e)}", 0

    except requests.exceptions.RequestException as e:
        return False, f"Request error: {str(e)}", 0

    except Exception as e:
        return False, f"Unexpected error: {str(e)}", 0


def main():
    """Main monitoring loop"""
    print("🚀 Starting AIR Coach API Monitor")
    print("📍 Monitoring: https://air-coach.com/api/test")
    print("⏱️  Interval: 30 seconds")
    print("🛑 Press Ctrl+C to stop\n")

    call_count = 0
    success_count = 0

    try:
        while True:
            call_count += 1
            timestamp = get_timestamp()

            print(f"[{timestamp}] Making API call #{call_count}...", end=" ", flush=True)

            success, message, response_time = test_api()

            if success:
                success_count += 1
                print(f"✅ API OK ({response_time}ms)")

                # Wait 30 seconds before next call
                print(f"⏳ Waiting 30 seconds for next check...\n")
                time.sleep(30)  # 30 seconds

            else:
                print(f"❌ API FAILED")
                print(f"📊 Statistics: {success_count}/{call_count} successful calls")
                print(f"🔍 Error Details:")
                print(f"   • Timestamp: {timestamp}")
                print(f"   • Response Time: {response_time}ms")
                print(f"   • Error: {message}")
                print("\n🛑 Monitoring stopped due to error.")
                sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Monitoring stopped by user")
        print(f"📊 Final Statistics: {success_count}/{call_count} successful calls")
        print("👋 Goodbye!")


if __name__ == "__main__":
    main()
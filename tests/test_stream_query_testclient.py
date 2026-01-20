"""
Integration tests for /api/stream_query endpoint using TestClient.

These tests use FastAPI's TestClient and do NOT require a manual server.
They validate the streaming endpoint behavior, authentication, and data persistence
without the overhead of starting a separate server process.

All tests are marked with @pytest.mark.integration and can be run with:
    pytest -m integration -v
"""

import pytest
import json
from src.env import DATABASE_NAME, COLLECTION_NAME
from src.database import get_collection

# Mark all tests in this file as integration tests (TestClient, no manual server)
pytestmark = pytest.mark.integration


def test_stream_query_invalid_token(test_client):
    """
    Verify that /stream_query rejects requests with invalid token.
    Expected: 401 or 403 status code
    """
    payload = {
        "message": "Ciao, chi sei? [Test con token non valido]",
        "userid": "google-oauth2|104612087445133776110"
    }
    headers = {
        "Authorization": "Bearer invalidtoken",
        "Content-Type": "application/json"
    }

    response = test_client.post("/api/stream_query", json=payload, headers=headers)
    assert response.status_code in (401, 403), \
        f"Expected 401 or 403, got {response.status_code}"


def test_stream_query_no_token(test_client):
    """
    Verify that /stream_query rejects requests without authorization header.
    Expected: 403 status code
    """
    payload = {
        "message": "Ciao, chi sei? [Test senza token]",
        "userid": "google-oauth2|104612087445133776110"
    }
    headers = {"Content-Type": "application/json"}  # No Authorization header

    response = test_client.post("/api/stream_query", json=payload, headers=headers)
    assert response.status_code == 403, \
        f"Expected 403 for missing auth, got {response.status_code}"


def test_stream_query_success(test_client, auth_headers, test_user_id):
    """
    Verify that /stream_query responds correctly to a valid streaming request.
    Validates SSE format and response structure.
    """
    payload = {
        "message": "Ciao chi sei? [Messaggio di test per streaming]",
        "userid": test_user_id
    }

    # TestClient supports streaming responses
    with test_client.stream("POST", "/api/stream_query", json=payload, headers=auth_headers) as response:
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}"

        # Verify SSE format: lines should contain "data:" prefix
        lines = list(response.iter_lines())
        data_lines = [line for line in lines if line.strip().startswith("data:")]

        assert len(data_lines) > 0, \
            "Expected at least one data line in SSE stream"


def test_stream_query_invalid_payload_422(test_client, auth_headers):
    """
    Verify that /stream_query returns 422 for invalid payload (missing userid).
    FastAPI validation should catch this before handler execution.
    """
    payload = {"message": "Messaggio senza userid"}

    response = test_client.post("/api/stream_query", json=payload, headers=auth_headers)
    assert response.status_code == 422, \
        f"Expected 422 for missing userid, got {response.status_code}"


def test_stream_query_saves_tool_result(test_client, auth_headers, test_user_id):
    """
    Verify that tool execution saves tool data to MongoDB correctly.

    This test:
    1. Sends a message that triggers the domanda_teoria tool
    2. Validates that tool_result events are received in the stream
    3. Checks MongoDB for the saved tool data
    4. Verifies the tool data structure matches expectations
    """
    payload = {
        "message": "fammi una domanda di teoria scelta casualmente. usa domanda_teoria",
        "userid": test_user_id,
    }

    # Stream the response and validate tool execution
    saw_tool_result = False
    saw_agent_message_after_tool = False

    with test_client.stream("POST", "/api/stream_query", json=payload, headers=auth_headers) as response:
        assert response.status_code == 200

        for line in response.iter_lines():
            if not line or not str(line).startswith("data:"):
                continue

            try:
                payload_str = str(line)[len("data:"):].strip()
                # Remove trailing escape sequences
                if payload_str.endswith('\\n\\n'):
                    payload_str = payload_str[:-4]
                elif payload_str.endswith('\n\n'):
                    payload_str = payload_str[:-2]

                evt = json.loads(payload_str)
            except Exception:
                continue

            if evt.get("type") == "tool_result":
                saw_tool_result = True
            elif evt.get("type") == "agent_message" and saw_tool_result:
                # With return_direct, no agent_message should come after tool_result
                saw_agent_message_after_tool = True

    # Validate stream events
    assert saw_tool_result, \
        "No 'tool_result' event received in stream"
    assert not saw_agent_message_after_tool, \
        "Received 'agent_message' after 'tool_result' (violates return_direct behavior)"

    # Validate MongoDB persistence
    coll = get_collection(DATABASE_NAME, COLLECTION_NAME)
    last_doc_cursor = coll.find({"userId": test_user_id}).sort("timestamp", -1).limit(1)
    last_docs = list(last_doc_cursor)

    assert last_docs, \
        "No document found in MongoDB after streaming call"

    doc = last_docs[0]
    assert "tool" in doc, \
        "Document missing 'tool' field"

    tool_entry = doc["tool"]

    # Support both single dict and list of dicts
    if isinstance(tool_entry, list):
        assert len(tool_entry) >= 1, "Tool entry list is empty"
        tool_item = tool_entry[0]
    else:
        tool_item = tool_entry

    assert isinstance(tool_item, dict), \
        f"Tool item should be dict, got {type(tool_item)}"

    # Support both old (name/result) and new (tool_name/data) schemas
    name = tool_item.get("name") or tool_item.get("tool_name")
    assert name == "domanda_teoria", \
        f"Expected tool name 'domanda_teoria', got '{name}'"

    result = tool_item.get("result") or tool_item.get("data")
    assert result is not None, \
        "Tool result/data is None"


def test_message_id_required_and_consistent(test_client, auth_headers, test_user_id):
    """
    Verify that message_id field is present and consistent across all stream chunks.

    This test validates:
    1. Every chunk has a 'message_id' field
    2. All chunks in a single request share the SAME message_id
    3. message_id format matches: {userid}_{ISO_timestamp}
    """
    payload = {
        "message": "Ciao, chi sei?",
        "userid": test_user_id,
    }

    message_ids = []
    chunk_count = 0

    with test_client.stream("POST", "/api/stream_query", json=payload, headers=auth_headers) as response:
        assert response.status_code == 200

        for line in response.iter_lines():
            if not line or not str(line).startswith("data:"):
                continue

            try:
                payload_str = str(line)[len("data:"):].strip()
                # Remove trailing escape sequences
                if payload_str.endswith('\\n\\n'):
                    payload_str = payload_str[:-4]
                elif payload_str.endswith('\n\n'):
                    payload_str = payload_str[:-2]

                evt = json.loads(payload_str)
            except Exception:
                continue

            chunk_count += 1

            # Validate message_id presence
            assert "message_id" in evt, \
                f"Chunk #{chunk_count} missing 'message_id' field: {evt}"

            message_id = evt["message_id"]
            message_ids.append(message_id)

            # Validate format: {userid}_{timestamp_ISO}
            assert message_id.startswith(test_user_id), \
                f"message_id '{message_id}' doesn't start with userid '{test_user_id}'"
            assert "_" in message_id, \
                f"message_id '{message_id}' missing '_' separator"

    # Validate we received chunks
    assert chunk_count > 0, \
        "No chunks received in stream"

    # Validate consistency: all chunks should have the same message_id
    unique_message_ids = set(message_ids)
    assert len(unique_message_ids) == 1, \
        f"message_id inconsistent: found {len(unique_message_ids)} different values: {unique_message_ids}"

    print(f"✓ Test passed: {chunk_count} chunks, all with identical message_id: {message_ids[0]}")

"""
Unit tests for src/agent/streaming_handler.py
Focus: on_chat_model_end captures real usage_metadata (fixes all-zeros bug)
"""
import pytest
from unittest.mock import MagicMock

from src.agent.streaming_handler import StreamingHandler


@pytest.mark.unit
class TestHandleModelEnd:
    """Tests for _handle_model_end capturing usage_metadata."""

    def test_handle_model_end_captures_usage_metadata(self):
        """Should capture usage_metadata from on_chat_model_end event."""
        handler = StreamingHandler(message_id="test-msg")

        output = MagicMock()
        output.usage_metadata = {
            "input_tokens": 185000,
            "output_tokens": 500,
            "total_tokens": 185500,
            "cached_tokens": 150000,
        }
        event = {"data": {"output": output}}

        handler._handle_model_end(event)

        assert handler.usage_metadata["input_tokens"] == 185000
        assert handler.usage_metadata["output_tokens"] == 500
        assert handler.usage_metadata["total_tokens"] == 185500
        assert handler.usage_metadata["cached_tokens"] == 150000

    def test_handle_model_end_overwrites_streaming_zeros(self):
        """Should overwrite zero-valued metadata from streaming chunks."""
        handler = StreamingHandler(message_id="test-msg")

        # Simulate streaming chunks setting all-zero metadata
        handler.usage_metadata = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
        }

        # on_chat_model_end provides real values
        output = MagicMock()
        output.usage_metadata = {
            "input_tokens": 185000,
            "output_tokens": 500,
            "total_tokens": 185500,
            "cached_tokens": 150000,
        }
        event = {"data": {"output": output}}

        handler._handle_model_end(event)

        assert handler.usage_metadata["input_tokens"] == 185000
        assert handler.usage_metadata["output_tokens"] == 500
        assert handler.usage_metadata["total_tokens"] == 185500
        assert handler.usage_metadata["cached_tokens"] == 150000

    def test_handle_model_end_ignores_empty_output(self):
        """Should preserve existing metadata when output is None."""
        handler = StreamingHandler(message_id="test-msg")
        handler.usage_metadata = {"input_tokens": 100}

        event = {"data": {"output": None}}
        handler._handle_model_end(event)

        assert handler.usage_metadata == {"input_tokens": 100}

    def test_handle_model_end_ignores_missing_usage_metadata(self):
        """Should preserve existing metadata when output has no usage_metadata."""
        handler = StreamingHandler(message_id="test-msg")
        handler.usage_metadata = {"input_tokens": 100}

        output = MagicMock(spec=[])  # no usage_metadata attribute
        event = {"data": {"output": output}}

        handler._handle_model_end(event)

        assert handler.usage_metadata == {"input_tokens": 100}


@pytest.mark.unit
class TestResetStateClearsUsageMetadata:
    """Tests for _reset_state clearing usage_metadata."""

    def test_reset_state_clears_usage_metadata(self):
        """Should clear usage_metadata on reset."""
        handler = StreamingHandler(message_id="test-msg")
        handler.usage_metadata = {
            "input_tokens": 185000,
            "output_tokens": 500,
        }

        handler._reset_state()

        assert handler.usage_metadata == {}

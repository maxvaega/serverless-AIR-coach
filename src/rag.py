"""
RAG orchestration module for AI Coach API.
Handles agent creation and query processing with streaming support.
"""
import datetime
import json
from typing import AsyncGenerator, Optional, Union

from langchain_core.messages import HumanMessage

from .env import FORCED_MODEL, VERTEX_AI_REGION, CACHE_DEBUG_LOGGING
from .utils import get_combined_docs, build_system_prompt, ensure_prompt_initialized
from .agent.agent_manager import AgentManager
from .agent.state_manager import _get_checkpointer
from .agent.streaming_handler import StreamingHandler
from .memory.seeding import MemorySeeder
from .memory.persistence import ConversationPersistence
from .monitoring.cache_monitor import log_request_context
from .monitoring.token_logger import log_token_usage, RequestTimer
from .monitoring.rate_limit_monitor import log_rate_limit_event

import logging
logger = logging.getLogger("uvicorn")


# Module-level cache for document/prompt content (refreshed via update_docs endpoint)
combined_docs: str = ""
system_prompt: str = ""


def generate_message_id(user_id: str) -> str:
    """Generate unique message ID for MongoDB persistence."""
    timestamp = datetime.datetime.now().isoformat(timespec='milliseconds')
    return f"{user_id}_{timestamp}"


def initialize_agent_state(force: bool = False) -> None:
    """
    Initialize documents and system prompt (lazy).
    Agent/LLM are created per-request to avoid event loop issues in serverless.
    """
    global combined_docs, system_prompt

    ensure_prompt_initialized()
    if force or not combined_docs or not system_prompt:
        combined_docs = get_combined_docs()
        system_prompt = build_system_prompt(combined_docs)


def ask(
    query: str,
    user_id: str,
    chat_history: bool = False,
    user_data: bool = False,
    token: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Process a query via LangGraph agent and return streaming response.
    """
    initialize_agent_state()

    if CACHE_DEBUG_LOGGING:
        log_request_context(user_id, FORCED_MODEL, VERTEX_AI_REGION)

    checkpointer = _get_checkpointer()
    agent_executor, config, prompt_version = AgentManager.create_agent(
        user_id=user_id,
        token=token,
        user_data=user_data,
        checkpointer=checkpointer
    )

    return _ask_streaming(agent_executor, config, query, user_id, chat_history) # Async streaming - Streaming = False non gestito



def _ask_streaming(agent_executor, config, query: str, user_id: str, chat_history: bool) -> AsyncGenerator[str, None]:
    """Handle async streaming agent invocation."""

    async def stream_response():
        MemorySeeder.seed_agent_memory(agent_executor, config, user_id, chat_history)
        message_id = generate_message_id(user_id)  # MOVED: Generate before handler
        streaming_handler = StreamingHandler(message_id=message_id)  # MODIFIED: Pass to handler
        timer = RequestTimer()

        try:
            logger.info(f"STREAM - Inizio gestione streaming per messaggio con ID= {message_id}")
            timer.__enter__()
            async for chunk in streaming_handler.handle_stream_events(agent_executor, query, config):
                yield chunk
        finally:
            timer.__exit__(None, None, None)
            response = streaming_handler.get_final_response()
            tool_records = streaming_handler.get_tool_records()
            serialized_output = streaming_handler.get_serialized_output()

            if not response and not streaming_handler.has_tool_executed():
                logger.warning("STREAM - Nessuna risposta dall'agente e nessun tool eseguito.")

            ConversationPersistence.log_run_completion(response, tool_records, serialized_output)
            ConversationPersistence.save_conversation(query, response, user_id, tool_records, message_id)

            # Log token usage metrics
            usage_metadata = streaming_handler.get_usage_metadata()
            if usage_metadata:
                log_token_usage(
                    user_id=user_id,
                    model=FORCED_MODEL,
                    usage_metadata=usage_metadata,
                    request_duration_ms=timer.duration_ms,
                    metadata={"message_id": message_id},
                )

            # Log rate limit events if detected
            rate_limit_error = getattr(streaming_handler, "_rate_limit_error", None)
            if rate_limit_error:
                log_rate_limit_event(
                    user_id=user_id,
                    model=FORCED_MODEL,
                    error_message=rate_limit_error,
                )

    return stream_response()


# Re-export for unit tests
from .history_hooks import build_llm_input_window_hook

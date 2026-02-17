import json
from typing import AsyncGenerator, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessageChunk

from ..tools import _serialize_tool_output
import logging
logger = logging.getLogger("uvicorn")


class StreamingHandler:
    """
    Gestisce gli eventi di streaming dell'agente LangGraph e l'elaborazione dei tool.
    """
    
    def __init__(self, message_id: str):
        if not message_id:
            raise ValueError("message_id is required for StreamingHandler")
        self.response_chunks: List[str] = []
        self.tool_records: List[Dict] = []
        self.tool_executed = False
        self.serialized_output = None
        self.message_id = message_id  # REQUIRED: Store for chunk injection
        self.usage_metadata: Dict[str, Any] = {}  # Token usage from LLM response
    
    async def handle_stream_events(
        self, 
        agent_executor, 
        query: str, 
        config: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Gestisce lo streaming degli eventi dall'agente e produce output JSON formattato.
        
        Args:
            agent_executor: L'agente LangGraph
            query: La query utente
            config: Configurazione dell'agente (thread_id, etc.)
            
        Yields:
            Stringhe JSON formattate per il client
        """
        self._reset_state()
        
        try:
            async for event in agent_executor.astream_events(
                {"messages": [HumanMessage(query)]},
                config=config,
                version="v2",
            ):
                kind = event.get("event")
                
                if kind == "on_tool_start":
                    async for chunk in self._handle_tool_start(event):
                        yield chunk
                    
                elif kind == "on_tool_end":
                    async for chunk in self._handle_tool_end(event):
                        yield chunk
                    
                elif kind == "on_chat_model_stream":
                    async for chunk in self._handle_model_stream(event):
                        yield chunk

                elif kind == "on_chat_model_end":
                    self._handle_model_end(event)

        except Exception as e:
            logger.error(f"Errore nello streaming con controllo tool: {e}")
            # Track rate limit errors for monitoring
            from ..monitoring.rate_limit_monitor import is_rate_limited
            if is_rate_limited(e):
                self._rate_limit_error = str(e)
            yield f"data: {{'error': 'Errore nello streaming: {str(e)}'}}\n\n"
    
    def _reset_state(self):
        """Reset dello stato interno per nuovo streaming."""
        self.response_chunks = []
        self.tool_records = []
        self.tool_executed = False
        self.serialized_output = None
        self.usage_metadata = {}
    
    async def _handle_tool_start(self, event: Dict) -> AsyncGenerator[str, None]:
        """Gestisce l'evento di inizio esecuzione tool (logging only)."""
        tool_name = event.get("name")
        tool_input = event.get("data", {}).get("input", {})
        logger.info(f"TOOL - {tool_name} started with input: {tool_input}")
        # Empty generator - no output yielded for tool start events
        if False:
            yield
    
    async def _handle_tool_end(self, event: Dict) -> AsyncGenerator[str, None]:
        """Gestisce l'evento di fine esecuzione tool."""
        self.tool_executed = True
        tool_name = event.get("name")
        tool_data = event.get("data", {})
        tool_output = tool_data.get("output")

        if tool_output:
            # Serializza correttamente l'output del tool
            self.serialized_output = _serialize_tool_output(tool_output)

            tool_record = {
                "tool_name": tool_name,
                "data": self.serialized_output
            }
            self.tool_records.append(tool_record)

            structured_response = {
                "type": "tool_result",
                "tool_name": tool_name,
                "data": self.serialized_output,
                "final": True,
                "message_id": self.message_id  # REQUIRED field
            }
            yield f"data: {json.dumps(structured_response)}\n\n"
            logger.info(f"TOOL - {tool_name} output processed")
    
    async def _handle_model_stream(self, event: Dict) -> AsyncGenerator[str, None]:
        """Gestisce l'evento di streaming del modello."""
        chunk = event["data"].get("chunk")
        if isinstance(chunk, AIMessageChunk):
            # Capture usage_metadata from the chunk (typically on the last chunk)
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                self.usage_metadata = chunk.usage_metadata
            content_text = chunk.text
            if content_text:
                self.response_chunks.append(content_text)
                ai_response = {
                    "type": "agent_message",
                    "data": content_text,
                    "message_id": self.message_id  # REQUIRED field
                }
                yield f"data: {json.dumps(ai_response)}\n\n"

    def _handle_model_end(self, event: Dict) -> None:
        """Capture usage_metadata from the complete model response."""
        output = event.get("data", {}).get("output")
        if output and hasattr(output, "usage_metadata") and output.usage_metadata:
            self.usage_metadata = output.usage_metadata
            logger.debug(f"STREAM - Captured usage_metadata: {self.usage_metadata}")

    def get_final_response(self) -> str:
        """Restituisce la risposta finale concatenata."""
        return "".join([c for c in self.response_chunks if c])
    
    def has_tool_executed(self) -> bool:
        """Verifica se è stato eseguito almeno un tool."""
        return self.tool_executed
    
    def get_tool_records(self) -> List[Dict]:
        """Restituisce i record dei tool eseguiti."""
        return self.tool_records
    
    def get_serialized_output(self):
        """Restituisce l'ultimo output serializzato dei tool."""
        return self.serialized_output

    def get_usage_metadata(self) -> Dict[str, Any]:
        """Returns captured token usage metadata from the LLM response."""
        return self.usage_metadata
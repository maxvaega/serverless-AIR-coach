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
    
    def __init__(self):
        self.response_chunks: List[str] = []
        self.tool_records: List[Dict] = []
        self.tool_executed = False
        self.serialized_output = None
    
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
                    
        except Exception as e:
            logger.error(f"Errore nello streaming con controllo tool: {e}")
            yield f"data: {{'error': 'Errore nello streaming: {str(e)}'}}\n\n"
    
    def _reset_state(self):
        """Reset dello stato interno per nuovo streaming."""
        self.response_chunks = []
        self.tool_records = []
        self.tool_executed = False
        self.serialized_output = None
    
    async def _handle_tool_start(self, event: Dict) -> AsyncGenerator[str, None]:
        """Gestisce l'evento di inizio esecuzione tool."""
        tool_name = event.get("name")
        tool_input = event.get("data", {}).get("input", {})
        logger.info(f"TOOL - {tool_name} started with input: {tool_input}")
        
        # Decommentare per inviare evento tool start al client
        # start_message = {
        #     "type": "tool_start",
        #     "tool_name": tool_name,
        #     "input": tool_input
        # }
        # yield f"data: {json.dumps(start_message)}\\n\\n"
        
        # Per compatibilità con codice esistente, non yieldiamo nulla
        # Questo è un async generator che non produce output
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
                "final": True
            }
            yield f"data: {json.dumps(structured_response)}\n\n"
            logger.info(f"TOOL - {tool_name} output processed")
    
    async def _handle_model_stream(self, event: Dict) -> AsyncGenerator[str, None]:
        """Gestisce l'evento di streaming del modello."""
        chunk = event["data"].get("chunk")
        if isinstance(chunk, AIMessageChunk):
            content_text = chunk.text()
            if content_text:
                self.response_chunks.append(content_text)
                ai_response = {
                    "type": "agent_message",
                    "data": content_text
                }
                yield f"data: {json.dumps(ai_response)}\n\n"
    
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
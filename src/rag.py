import datetime
import json
from typing import AsyncGenerator, Optional, Union, Any

from langchain_core.messages import HumanMessage

from .env import DATABASE_NAME, COLLECTION_NAME, HISTORY_LIMIT, VERTEX_AI_REGION, FORCED_MODEL, CACHE_DEBUG_LOGGING
from .database import get_data
from .utils import (
    get_combined_docs,
    build_system_prompt,
    ensure_prompt_initialized,
)
import logging
logger = logging.getLogger("uvicorn")
from .agent.agent_manager import AgentManager
from .agent.state_manager import _get_checkpointer
from .agent.streaming_handler import StreamingHandler
from .memory.seeding import MemorySeeder
from .memory.persistence import ConversationPersistence
from .monitoring.cache_monitor import log_cache_metrics, log_request_context


# ------------------------------------------------------------------------------
# Costanti e stato di modulo
# ------------------------------------------------------------------------------
combined_docs: str = ""
system_prompt: str = ""
llm: Optional[Any] = None  # non usare a livello globale in serverless  
# Checkpointer globale riutilizzabile (non legato all'event loop) per mantenere memoria volatile tra richieste
checkpointer: Optional[Any] = None
agent_executor = None  # non usare a livello globale in serverless


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def initialize_agent_state(force: bool = False) -> None:
    """
    Inizializza solo i documenti e il system_prompt. L'agente/LLM vengono
    creati per-request per evitare problemi di event loop in ambiente serverless.
    """
    global combined_docs, system_prompt

    try:
        # Inizializza il PromptManager process-global se necessario.
        ensure_prompt_initialized()
        # Aggiorna le variabili modulo per retro-compatibilità con il resto del file.
        if force or not combined_docs or not system_prompt:
            combined_docs = get_combined_docs()
            # Nota: il vero system prompt usato dall'agente arriva dal PromptManager.
            # Manteniamo anche la copia locale per compat.
            system_prompt = build_system_prompt(combined_docs)
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione dello stato agente: {e}")



# Evita inizializzazione eager di oggetti legati all'event loop in ambiente serverless.
# Inizializza solo il prompt/documenti al primo utilizzo.


# ------------------------------------------------------------------------------
# API di modulo
# ------------------------------------------------------------------------------


def ask(
    query: str,
    user_id: str,
    chat_history: bool = False,
    stream: bool = False,
    user_data: bool = False,
    token: Optional[str] = None,
) -> Union[str, AsyncGenerator[str, None]]:
    """
    Elabora una query tramite agente LangGraph e restituisce la risposta, opzionalmente in streaming.
    L'agente può usare tool. La memoria usa il checkpointer se presente, altrimenti si ricostruisce da MongoDB.
    Se richiesto, i metadata profilo utente vengono recuperati da Auth0.
    """
    # Inizializza prompt/documenti (lazy)
    initialize_agent_state()

    # Log contesto richiesta per monitoraggio cache
    if CACHE_DEBUG_LOGGING:
        log_request_context(user_id, FORCED_MODEL, VERTEX_AI_REGION)

    # Crea agente per-request usando AgentManager
    checkpointer = _get_checkpointer()
    agent_executor, config, prompt_version = AgentManager.create_agent(
        user_id=user_id,
        token=token,
        user_data=user_data,
        checkpointer=checkpointer
    )

    
    # Branch per modalità sync/async
    if not stream:
        return _ask_sync(agent_executor, config, query, user_id, chat_history)
    else:
        return _ask_async(agent_executor, config, query, user_id, chat_history)


def _ask_sync(agent_executor, config, query: str, user_id: str, chat_history: bool) -> str:
    """
    Gestisce l'invocazione sincrona dell'agente.
    """
    try:
        # Seed memoria da DB se necessario
        MemorySeeder.seed_agent_memory(agent_executor, config, user_id, chat_history)
        
        # Invocazione sincrona
        result = agent_executor.invoke({"messages": [HumanMessage(query)]}, config=config)
        return result["messages"][-1].content
        
    except Exception as e:
        logger.error(f"Errore nell'invocare l'agente: {e}")
        return "Errore nell'invocare l'agente."


def _ask_async(agent_executor, config, query: str, user_id: str, chat_history: bool) -> AsyncGenerator[str, None]:
    """
    Gestisce l'invocazione asincrona con streaming dell'agente.
    """
    async def stream_response():
        # Seed memoria da DB se necessario  
        MemorySeeder.seed_agent_memory(agent_executor, config, user_id, chat_history)
        
        # Gestione streaming con handler dedicato
        streaming_handler = StreamingHandler()
        message_id = f"{user_id}_{datetime.datetime.now().isoformat(timespec='milliseconds')}"
        
        try:
            logger.info(f"STREAM - Inizio gestione streaming per messaggio ID: {message_id}")
            async for chunk in streaming_handler.handle_stream_events(agent_executor, query, config):
                yield chunk
                
        finally:
            # Persistenza finale
            response = streaming_handler.get_final_response()
            tool_records = streaming_handler.get_tool_records()
            serialized_output = streaming_handler.get_serialized_output()
            
            # Gestione risposta vuota
            if not response and not streaming_handler.has_tool_executed():
                logger.warning("STREAM - Nessuna risposta dall'agente e nessun tool eseguito.")
                # Mandavo uno spazio vuoto come workaround. TBC
                # response = " "
                # fallback_ai_response = {
                #     "type": "agent_message",
                #     "data": response
                # }
                # yield f"data: {json.dumps(fallback_ai_response)}"
            
            # Log completamento e persistenza
            ConversationPersistence.log_run_completion(response, tool_records, serialized_output)
            ConversationPersistence.save_conversation(query, response, user_id, tool_records, message_id)
    
    return stream_response()


# Re-export per i test unitari
from .history_hooks import build_llm_input_window_hook
build_llm_input_window_hook = build_llm_input_window_hook
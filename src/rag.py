import asyncio
import datetime
import json
from typing import AsyncGenerator, Optional, Union
from contextlib import asynccontextmanager

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .env import FORCED_MODEL, DATABASE_NAME, COLLECTION_NAME
from .database import get_data, insert_data
from .auth0 import get_user_metadata
from .utils import format_user_metadata, get_combined_docs, update_docs_from_s3
from .cache import get_cached_user_data, set_cached_user_data
from .tools import test_licenza
from .logging_config import logger


# ------------------------------------------------------------------------------
# Costanti e stato di modulo
# ------------------------------------------------------------------------------
HISTORY_LIMIT = 10

# Usa un dizionario per evitare problemi con le variabili globali in serverless
_agent_state = {
    "combined_docs": "",
    "system_prompt": "",
    "llm": None,
    "checkpointer": None,
    "agent_executor": None,
    "lock": asyncio.Lock()  # Per evitare race conditions in serverless
}


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def build_system_prompt(docs: str) -> str:
    """
    Costruisce e restituisce il system_prompt utilizzando il contenuto combinato dei documenti.
    """
    return f"{docs}"


def _extract_text(content) -> str:
    """
    Normalizza il contenuto dei messaggi AI in stringa.
    """
    try:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    txt = p.get("text") or p.get("content")
                    if isinstance(txt, str):
                        parts.append(txt)
            return "".join(parts)
    except Exception:
        pass
    return ""


async def initialize_agent_async(force: bool = False) -> None:
    """
    Inizializza prompt, LLM e agente in modo asincrono con lock per evitare race conditions.
    """
    async with _agent_state["lock"]:
        if not force and _agent_state["agent_executor"] is not None:
            return

        try:
            # Reperisce/aggiorna i documenti
            if force or not _agent_state["combined_docs"]:
                _agent_state["combined_docs"] = get_combined_docs()
                _agent_state["system_prompt"] = build_system_prompt(_agent_state["combined_docs"])

            # Definisce LLM
            model = FORCED_MODEL
            logger.info(f"Selected LLM model: {model}")
            _agent_state["llm"] = ChatGoogleGenerativeAI(
                model=model,
                temperature=0.7,
            )

            # Usa MemorySaver invece di InMemorySaver (deprecato)
            tools = [test_licenza]
            _agent_state["checkpointer"] = MemorySaver()
            _agent_state["agent_executor"] = create_react_agent(
                _agent_state["llm"],
                tools,
                prompt=_agent_state["system_prompt"],
                checkpointer=_agent_state["checkpointer"],
            )
            logger.info("Agent initialized successfully.")
        except Exception as e:
            logger.error(f"Errore durante l'inizializzazione dell'agente: {e}")
            raise


def initialize_agent(force: bool = False) -> None:
    """
    Wrapper sincrono per compatibilità con codice esistente.
    """
    try:
        # Crea un nuovo event loop se necessario
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(initialize_agent_async(force))
    except Exception as e:
        logger.error(f"Initial agent initialization failed: {e}")


# Inizializzazione lazy invece di eager per evitare problemi in serverless
# L'inizializzazione avverrà al primo utilizzo


# ------------------------------------------------------------------------------
# API di modulo
# ------------------------------------------------------------------------------
def update_docs():
    """
    Wrapper per aggiornare i documenti su S3 e lo stato locale del modulo.
    """
    update_result = update_docs_from_s3()

    if update_result and "system_prompt" in update_result:
        _agent_state["combined_docs"] = update_result["system_prompt"]
        _agent_state["system_prompt"] = build_system_prompt(_agent_state["combined_docs"])
        logger.info("System prompt aggiornato con successo.")

    return update_result

async def ask_stream(
    query: str,
    user_id: str,
    chat_history: bool = False,
    user_data: bool = False,
    token: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Funzione asincrona per streaming delle risposte.
    Restituisce sempre un async generator per lo streaming.
    """
    # Inizializza l'agente se necessario
    if _agent_state["agent_executor"] is None:
        await initialize_agent_async()
    
    agent_executor = _agent_state["agent_executor"]
    response_chunks = []
    config = {"configurable": {"thread_id": str(user_id)}}
    
    try:
        # Controlla lo stato della memoria
        try:
            state = await agent_executor.aget_state(config)
            existing_messages = state.values.get("messages") if state and hasattr(state, "values") else None
            msg_count = len(existing_messages) if existing_messages else 0
            logger.info(f"HISTORY - Numero di messaggi in memoria: {msg_count}")
        except Exception as e:
            logger.error(f"Errore nel recuperare lo stato dell'agente: {e}")
            existing_messages = None
        
        # Se non ci sono messaggi in memoria, carica da DB
        if not existing_messages:
            logger.info("HISTORY - Nessun messaggio in memoria, cerco su DB...")
            seed_messages = []
            
            # Carica dati utente se richiesto
            if user_data:
                try:
                    ui = get_cached_user_data(user_id)
                    if not ui:
                        user_metadata = get_user_metadata(user_id, token=token)
                        ui = format_user_metadata(user_metadata)
                        if ui:
                            set_cached_user_data(user_id, ui)
                    if ui:
                        seed_messages.append(AIMessage(ui))
                        logger.info("HISTORY / USER DATA - User info inserito in memoria")
                except Exception as e:
                    logger.error(f"Errore nel recuperare i dati utente: {e}")
            
            # Carica history da DB se richiesta
            if chat_history:
                try:
                    history = get_data(
                        DATABASE_NAME,
                        COLLECTION_NAME,
                        filters={"userId": user_id},
                        limit=HISTORY_LIMIT,
                    )
                    for msg in history:
                        if msg.get("human"):
                            seed_messages.append(HumanMessage(msg["human"]))
                        
                        tool_entry = msg.get("tool")
                        if tool_entry:
                            try:
                                tool_name = tool_entry.get("name") if isinstance(tool_entry, dict) else None
                                tool_payload = tool_entry.get("result") if isinstance(tool_entry, dict) else tool_entry
                                tool_text = json.dumps(tool_payload) if not isinstance(tool_payload, str) else tool_payload
                                seed_messages.append(AIMessage(f"previous tool [{tool_name}] result : \n{tool_text}"))
                            except Exception:
                                pass
                        
                        if msg.get("system"):
                            seed_messages.append(AIMessage(msg["system"]))
                    
                    if history:
                        logger.info(f"HISTORY - Recuperati {len(history)} messaggi da DB")
                except Exception as e:
                    logger.error(f"Errore nel recuperare la chat history: {e}")
            
            # Aggiorna lo stato con i messaggi seed
            if seed_messages:
                try:
                    await agent_executor.aupdate_state(config, {"messages": seed_messages})
                except Exception as e:
                    logger.error(f"Error seeding agent state: {e}")
        
        tool_records = []
        
        # Streaming principale
        try:
            async for event in agent_executor.astream_events(
                {"messages": [HumanMessage(query)]},
                config=config,
                version="v2",
            ):
                kind = event.get("event")
                
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if isinstance(chunk, AIMessageChunk):
                        content_text = _extract_text(chunk.content)
                        if content_text:
                            response_chunks.append(content_text)
                            yield f"data: {json.dumps({'data': content_text})}\n\n"
                
                elif kind in ("on_agent_finish", "on_chain_end"):
                    data = event.get("data", {})
                    final_output = data.get("output", {}) if isinstance(data, dict) else {}
                    final_messages = final_output.get("messages", []) if isinstance(final_output, dict) else []
                    
                    logger.info(f"RUN - messages count={len(final_messages)}")
                    
                    # Raccoglie tool messages
                    try:
                        for m in final_messages:
                            if isinstance(m, ToolMessage):
                                tool_records.append({
                                    "name": getattr(m, "name", None),
                                    "result": m.content,
                                })
                    except Exception as e:
                        logger.warning(f"Tool extraction error: {e}")
                    
                    # Ultimo contenuto se non già inviato
                    if final_messages:
                        last_msg = final_messages[-1]
                        if isinstance(last_msg, AIMessage):
                            content_text = _extract_text(last_msg.content)
                            if content_text and not response_chunks:
                                response_chunks.append(content_text)
                                yield f"data: {json.dumps({'data': content_text})}\n\n"
        
        except Exception as e:
            logger.error(f"Errore nello streaming: {e}")
            yield f"data: {json.dumps({'error': f'Errore streaming: {str(e)}'})}\n\n"
            return
        
        # Fallback per output dei tool se non c'è altro contenuto
        if not response_chunks and tool_records:
            try:
                last_tool = tool_records[-1]
                tool_result = last_tool.get("result")
                tool_text = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
                if tool_text:
                    yield f"data: {json.dumps({'data': tool_text})}\n\n"
                    response_chunks.append(tool_text)
            except Exception as e:
                logger.warning(f"Fallback tool failed: {e}")
        
        # Salva su database
        response = "".join([c for c in response_chunks if c])
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"RUN TERMINATA: response_len={len(response)}")
        
        try:
            data = {
                "human": query,
                "system": response,
                "userId": user_id,
                "timestamp": timestamp,
            }
            if tool_records:
                data["tool"] = tool_records[-1]
            
            if response or data.get("tool"):
                insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                logger.info(f"DB - Dati salvati")
        except Exception as e:
            logger.error(f"DB - Errore salvataggio: {e}")
        
        # Segnala fine stream per Vercel
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    finally:
        logger.info("Stream completato")
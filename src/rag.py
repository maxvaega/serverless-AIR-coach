import datetime
import json
from typing import AsyncGenerator, Optional, Union
import asyncio

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

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

combined_docs: str = ""
system_prompt: str = ""
llm: Optional[ChatGoogleGenerativeAI] = None  # non usare a livello globale in serverless
# Checkpointer globale riutilizzabile (non legato all'event loop) per mantenere memoria volatile tra richieste
checkpointer: Optional[InMemorySaver] = None
agent_executor = None  # non usare a livello globale in serverless


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

def _serialize_tool_output(tool_output) -> dict:
    """
    Serializza l'output del tool in un formato JSON-compatibile.
    """
    try:
        # Se è un ToolMessage, estrai il contenuto
        if isinstance(tool_output, ToolMessage):
            return {
                "content": tool_output.content,
                "tool_call_id": getattr(tool_output, 'tool_call_id', None)
            }
        # Se è già un dict o altro tipo serializzabile
        elif isinstance(tool_output, (dict, list, str, int, float, bool)):
            return tool_output
        # Per altri tipi, converti in stringa
        else:
            return {"content": str(tool_output)}
    except Exception as e:
        logger.error(f"Errore nella serializzazione del tool output: {e}")
        return {"content": str(tool_output), "error": "serialization_failed"}


def initialize_agent_state(force: bool = False) -> None:
    """
    Inizializza solo i documenti e il system_prompt. L'agente/LLM vengono
    creati per-request per evitare problemi di event loop in ambiente serverless.
    """
    global combined_docs, system_prompt

    try:
        if force or not combined_docs or not system_prompt:
            combined_docs = get_combined_docs()
            system_prompt = build_system_prompt(combined_docs)
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione dello stato agente: {e}")


def _get_checkpointer() -> InMemorySaver:
    """Ritorna un checkpointer condiviso a livello di processo (thread-safe best-effort).
    InMemorySaver non dipende dall'event loop, quindi è sicuro riutilizzarlo tra richieste
    per mantenere la memoria volatile dei thread (per `thread_id`).
    """
    global checkpointer
    if checkpointer is None:
        checkpointer = InMemorySaver()
    return checkpointer


# Evita inizializzazione eager di oggetti legati all'event loop in ambiente serverless.
# Inizializza solo il prompt/documenti al primo utilizzo.


# ------------------------------------------------------------------------------
# API di modulo
# ------------------------------------------------------------------------------
def update_docs():
    """
    Wrapper per aggiornare i documenti su S3 e lo stato locale del modulo (combined_docs/system_prompt).
    Non ricrea l'agente per mantenere il comportamento esistente.
    """
    global combined_docs, system_prompt
    update_result = update_docs_from_s3()

    if update_result and "system_prompt" in update_result:
        combined_docs = update_result["system_prompt"]
        system_prompt = build_system_prompt(combined_docs)
        logger.info("System prompt aggiornato con successo.")

    return update_result


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

    # Costruisce agent per-request per evitare problemi di event loop chiuso
    model = FORCED_MODEL
    logger.info(f"Selected LLM model: {model}")
    local_llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=0.7,
    )
    tools = [test_licenza]
    local_checkpointer = _get_checkpointer()
    agent_executor = create_react_agent(
        local_llm,
        tools,
        prompt=system_prompt,
        checkpointer=local_checkpointer,
    )

    # Branch non-stream (sync)
    if not stream:
        try:
            messages = []
            user_info = None

            if user_data:
                try:
                    user_info = get_cached_user_data(user_id)
                    if not user_info:
                        user_metadata = get_user_metadata(user_id, token=token)
                        user_info = format_user_metadata(user_metadata)
                        set_cached_user_data(user_id, user_info)
                    if user_info:
                        messages.append(AIMessage(user_info))
                        logger.info(f"User info aggiunto ai messaggi: {user_info}")
                except Exception as e:
                    logger.error(f"Errore nel recuperare i dati dell'utente per l'ID {user_id}: {e}")
                    return f"data: {{'error': 'Errore nel recuperare i dati dell\\'utente: {str(e)}'}}\n\n"

            # Gestione manuale history
            try:
                if chat_history:
                    history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=HISTORY_LIMIT)
                    for msg in history:
                        messages.append(HumanMessage(msg.get("human", "")))
                        messages.append(AIMessage(msg.get("system", "")))
                        logger.info(f"Chat history: {msg.get('human')} \n-> \n{msg.get('system')}")
            except Exception as e:
                logger.error(f"HISTORY - Errore nel recuperare la chat history: {e}")
                return f"data: {{'error': 'Errore nel recuperare la chat history: {str(e)}'}}\n\n"

            # Messaggio corrente
            messages.append(HumanMessage(query))

            # Invocazione sincrona
            try:
                result = agent_executor.invoke({"messages": messages})
                final_response = result["messages"][-1].content
                return final_response
            except Exception as e:
                logger.error(f"Errore nell'invocare l'agente: {e}")
                return "Errore nell'invocare l'agente."
        except Exception as e:
            logger.error(f"Errore non gestito nel branch non-stream: {e}")
            return "Errore interno inatteso."

    # Branch stream (async)
    else:
        response_chunks = []

        async def stream_response():
            nonlocal response_chunks

            # Best practice: thread per utente
            config = {"configurable": {
                "thread_id": str(user_id),
                "recursion_limit": 2
                }
            }

            # Memoria ibrida: volatile se presente, altrimenti seed da DB
            try:
                state = agent_executor.get_state(config)
                existing_messages = state.values.get("messages") if state and hasattr(state, "values") else None
                msg_count = len(existing_messages) if existing_messages else 0
                logger.info(f"HISTORY - Recupero lo stato dell'agente. Numero di messaggi in memoria: {msg_count}")
            except Exception as e:
                logger.error(f"Errore nel recuperare lo stato dell'agente: {e}")
                existing_messages = None

            if not existing_messages:
                logger.info("HISTORY - Nessun messaggio trovato in memoria volatile, cerco cronologia conversazione su DB...")
                seed_messages = []

                # Cold start: inject user info in volatile memory
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
                            logger.info("HISTORY / USER DATA - User info inserito nella memoria volatile del thread (cold start)")
                    except Exception as e:
                        logger.error(f"Errore nel recuperare i dati utente per cold start: {e}")

                # Seed da DB se richiesto
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
                                    tool_name = tool_entry.get("name") if isinstance(tool_entry, dict) else "unknown_tool"
                                    tool_result = tool_entry.get("result") if isinstance(tool_entry, dict) else tool_entry
                                    tool_message = ToolMessage(
                                        content=json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
                                        tool_call_id=f"call_{tool_name}_{msg.get('timestamp', 'unknown')}"
                                    )
                                    seed_messages.append(tool_message)
                                except Exception as te:
                                    logger.error(f"Errore nella creazione del ToolMessage per il seeding: {te}")

                            if msg.get("system"):
                                seed_messages.append(AIMessage(msg["system"]))
                        if history:
                            logger.info(f"HISTORY - Cronologia recuperata da DB: {len(history)} messaggi")
                    except Exception as e:
                        logger.error(f"Errore nel recuperare la chat history: {e}")

                # Aggiorna memoria volatile
                if seed_messages:
                    try:
                        agent_executor.update_state(config, {"messages": seed_messages})
                    except Exception as e:
                        logger.error(f"Error seeding agent state: {e}")

            tool_records = []
            tool_executed = False

            try:
                # Intercetta gli output del tool per classificarli usando le coppie evento : type seguenti
                # On_tool_start (rimosso)
                # On_tool_end : tool result
                # On_chat_model_stream : agent_message

                async for event in agent_executor.astream_events(
                    {"messages": [HumanMessage(query)]},
                    config=config,
                    version="v2",
                ):
                    kind = event.get("event")

                    if kind == "on_tool_start":
                        tool_name = event.get("name")
                        tool_input = event.get("data", {}).get("input", {})

                        # decommentare per inviare il tool start al client
                        # start_message = {
                        #     "type": "tool_start",
                        #     "tool_name": tool_name,
                        #     "input": tool_input
                        # }
                        # yield f"data: {json.dumps(start_message)}\n\n" 
                        logger.info(f"Tool {tool_name} started with input: {tool_input}")

                    elif kind == "on_tool_end":
                        tool_executed = True
                        tool_name = event.get("name")
                        tool_data = event.get("data", {})
                        tool_output = tool_data.get("output")

                        if tool_output:
                            # Serializza correttamente l'output del tool
                            serialized_output = _serialize_tool_output(tool_output)

                            tool_record = {
                                "name": tool_name,
                                "result": serialized_output
                            }
                            tool_records.append(tool_record)

                            structured_response = {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "data": serialized_output,
                                "final": True
                            }
                            yield f"data: {json.dumps(structured_response)}\n\n"
                            logger.info(f"Tool output processed: {tool_name}")
                            # Decommentare per assicurarsi una sola esecuzione del tool a livello programmatico
                            # break

                    elif kind == "on_chat_model_stream": #and not tool_executed:
                        chunk = event["data"].get("chunk")
                        if isinstance(chunk, AIMessageChunk):
                            content_text = _extract_text(chunk.content)
                            if content_text:
                                response_chunks.append(content_text)
                                ai_response = {
                                    "type": "agent_message",
                                    "data": content_text
                                }
                                yield f"data: {json.dumps(ai_response)}\n\n"

            except Exception as e:
                logger.error(f"Errore nello streaming con controllo tool: {e}")
                yield f"data: {{'error': 'Errore nello streaming: {str(e)}'}}\n\n"

            finally:
                try:
                    # Persistenza su DB a fine streaming
                    response = "".join([c for c in response_chunks if c])
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"RUN TERMINATA alle {timestamp}: response_len={len(response)} tool_records={len(tool_records)}")
                    logger.info(f"\nRUN - Risposta LLM:\n{response}")
                    if serialized_output:
                        logger.info(f"\nRUN - Risposta Tool:\n{serialized_output}")

                    data = {
                        "human": query,
                        "system": response,
                        "userId": user_id,
                        "timestamp": timestamp,
                    }
                    if tool_records:
                        data["tool"] = tool_records[-1]  # salva solo l'ultimo tool record

                    if response or data.get("tool"):
                        insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                        logger.info(f"DB - Risposta inserita nella collection: {COLLECTION_NAME} ")
                        
                except Exception as e:
                    logger.error(f"DB - Errore nell'inserire i dati nella collection: {e}")

        return stream_response()
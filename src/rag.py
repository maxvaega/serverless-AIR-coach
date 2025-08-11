import datetime
import json
from typing import AsyncGenerator, Optional, Union
import asyncio
import time

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
LOG_MAX_TEXT_CHARS = 200

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


def _truncate_for_log(text: Optional[str], max_chars: int = LOG_MAX_TEXT_CHARS) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def create_agent_instance() -> object:
    """
    Crea un agente per-request usando il checkpointer condiviso a livello di processo.
    """
    model = FORCED_MODEL
    logger.info(f"Selected LLM model: {model}")
    local_llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=0.7,
    )
    tools = [test_licenza]
    local_checkpointer = _get_checkpointer()
    return create_react_agent(
        local_llm,
        tools,
        prompt=system_prompt,
        checkpointer=local_checkpointer,
    )


def prepare_seed_messages(
    user_id: str,
    chat_history: bool,
    user_data: bool,
    token: Optional[str],
) -> list:
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
            added = 0
            for msg in history:
                if msg.get("human"):
                    seed_messages.append(HumanMessage(msg["human"]))
                    added += 1
                tool_entry = msg.get("tool")
                if tool_entry:
                    try:
                        tool_name = tool_entry.get("name") if isinstance(tool_entry, dict) else None
                        tool_payload = tool_entry.get("result") if isinstance(tool_entry, dict) else tool_entry
                        tool_text = json.dumps(tool_payload) if not isinstance(tool_payload, str) else tool_payload
                        seed_messages.append(AIMessage(f"previous tool [{tool_name}] result : \n{_truncate_for_log(tool_text)}"))
                        added += 1
                    except Exception:
                        pass
                if msg.get("system"):
                    seed_messages.append(AIMessage(msg["system"]))
                    added += 1
            if history:
                logger.info(f"HISTORY - Cronologia recuperata da DB: {len(history)} messaggi, seed aggiunti: {added}")
        except Exception as e:
            logger.error(f"Errore nel recuperare la chat history: {e}")

    return seed_messages


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

    # Crea agente per-request
    agent_executor = create_agent_instance()

    # Branch non-stream (sync)
    if not stream:
        try:
            t0 = time.perf_counter()
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
                        logger.info("User info aggiunto ai messaggi (troncato)")
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
                        pass  # Evita log verbosi di contenuti interi
            except Exception as e:
                logger.error(f"HISTORY - Errore nel recuperare la chat history: {e}")
                return f"data: {{'error': 'Errore nel recuperare la chat history: {str(e)}'}}\n\n"

            # Messaggio corrente
            messages.append(HumanMessage(query))

            # Invocazione sincrona
            try:
                result = agent_executor.invoke({"messages": messages})
                final_response = result["messages"][-1].content
                duration_ms = int((time.perf_counter() - t0) * 1000)
                logger.info(f"ASK SYNC - done in {duration_ms} ms; response_len={len(final_response) if isinstance(final_response, str) else 'n/a'}")
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
            t0 = time.perf_counter()

            # Best practice: thread per utente
            config = {"configurable": {"thread_id": str(user_id)}}
            logger.info(f"STREAM - start; thread_id={user_id}; query='{_truncate_for_log(query)}'")

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
                                    tool_name = tool_entry.get("name") if isinstance(tool_entry, dict) else None
                                    tool_payload = tool_entry.get("result") if isinstance(tool_entry, dict) else tool_entry
                                    tool_text = json.dumps(tool_payload) if not isinstance(tool_payload, str) else tool_payload
                                    seed_messages.append(AIMessage(f"previous tool [{tool_name}] result : \n{tool_text}"))
                                except Exception:
                                    pass

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

            try:
                # Stream solo il messaggio corrente; lo storico è nello state
                buffer_pretool: list[str] = []
                encountered_tool = False
                allow_streaming_tokens = False
                late_pretool_final: Optional[str] = None
                async for event in agent_executor.astream_events(
                    {"messages": [HumanMessage(query)]},
                    config=config,
                    version="v2",
                ):
                    kind = event.get("event")

                    # Rilevazione tool start/end dall'evento (best-effort; non sempre presente)
                    if isinstance(kind, str):
                        lower_kind = kind.lower()
                        if "on_tool" in lower_kind and ("start" in lower_kind):
                            encountered_tool = True
                            # scarta il buffer pre-tool (preamboli inutili)
                            dropped = len("".join(buffer_pretool))
                            buffer_pretool = []
                            logger.info(f"STREAM - tool detected (start); dropped_pretool_chars={dropped}")
                        elif "on_tool" in lower_kind and ("end" in lower_kind or "finish" in lower_kind):
                            # da qui in poi streammiamo i token
                            allow_streaming_tokens = True
                            logger.info("STREAM - tool finished; start streaming post-tool tokens")

                    if kind == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if isinstance(chunk, AIMessageChunk):
                            content_text = _extract_text(chunk.content)
                            if content_text:
                                if allow_streaming_tokens:
                                    response_chunks.append(content_text)
                                    data_dict = {"data": content_text}
                                    yield f"data: {json.dumps(data_dict)}\n\n"
                                else:
                                    # Bufferizza finché non sappiamo se verrà usato un tool
                                    buffer_pretool.append(content_text)

                    elif kind in ("on_agent_finish", "on_chain_end"):
                        data = event.get("data", {})
                        final_output = data.get("output", {}) if isinstance(data, dict) else {}
                        final_messages = final_output.get("messages", []) if isinstance(final_output, dict) else []

                        logger.info(
                            f"RUN - messages count={len(final_messages)}; types={[type(m).__name__ for m in final_messages]}"
                        )

                        # Raccoglie ToolMessage prodotti nel run
                        try:
                            for m in final_messages:
                                if isinstance(m, ToolMessage):
                                    tool_records.append({
                                        "name": getattr(m, "name", None),
                                        "result": m.content,
                                    })
                                    encountered_tool = True
                        except Exception as e:
                            logger.warning(f"Tool extraction error: {e}")

                        # Ultimo contenuto assistente (se non già streammato)
                        if final_messages:
                            last_msg = final_messages[-1]
                            if isinstance(last_msg, AIMessage):
                                content_text = _extract_text(last_msg.content)
                                # Caso A: non c'è stato tool → NON emettere subito; salva e decidi a fine run
                                if content_text and not encountered_tool:
                                    late_pretool_final = content_text
                                # Caso B: c'è stato tool → ignora buffer_pretool, invia solo il finale se non già streammato
                                elif content_text and encountered_tool and not response_chunks:
                                    response_chunks.append(content_text)
                                    yield f"data: {json.dumps({'data': content_text})}\n\n"

            except RuntimeError as e:
                # Tipico in serverless: event loop chiuso tra richieste
                logger.error(f"Streaming RuntimeError: {e}")
                yield f"data: {{'error': 'Errore nello streaming della risposta dell\\'agente: Event loop non disponibile'}}\n\n"
            except Exception as e:
                logger.error(f"Errore nello streaming della risposta dell'agente: {e}")
                yield f"data: {{'error': 'Errore nello streaming della risposta dell\\'agente: {str(e)}'}}\n\n"

            # Fallback: se non c'è testo ma abbiamo tool_results, emetti ultimo tool
            if not response_chunks and tool_records:
                try:
                    last_tool = tool_records[-1]
                    tool_result = last_tool.get("result")
                    tool_text = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
                    if tool_text:
                        yield f"data: {json.dumps({'data': tool_text})}\n\n"
                        response_chunks.append(tool_text)
                        logger.info("RUN - Risposta del tool emessa a causa di output dell'assistente vuoto")
                except Exception as e:
                    logger.warning(f"RUN - Fallback from tool failed: {e}")

            # Fine streaming: se non c'è stato tool, flush del pre-tool buffer e dell'eventuale finale
            if not encountered_tool:
                if buffer_pretool:
                    buffered = "".join(buffer_pretool)
                    if buffered:
                        response_chunks.append(buffered)
                        yield f"data: {json.dumps({'data': buffered})}\n\n"
                if late_pretool_final:
                    # Evita duplicare se identico all'ultimo chunk
                    if not response_chunks or response_chunks[-1] != late_pretool_final:
                        response_chunks.append(late_pretool_final)
                        yield f"data: {json.dumps({'data': late_pretool_final})}\n\n"

            # Persistenza su DB a fine streaming
            response = "".join([c for c in response_chunks if c])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                f"STREAM - done at {timestamp}; duration_ms={duration_ms}; response_len={len(response)}; "
                f"encountered_tool={encountered_tool}; tool_records={len(tool_records)}; "
                f"preview='{_truncate_for_log(response)}'"
            )

            try:
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
                # Non inviare error al client dopo la chiusura dello stream

        return stream_response()
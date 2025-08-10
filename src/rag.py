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
checkpointer: Optional[InMemorySaver] = None  # non usare a livello globale in serverless
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
    local_checkpointer = InMemorySaver()
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
            config = {"configurable": {"thread_id": str(user_id)}}

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
                                data_dict = {"data": content_text}
                                yield f"data: {json.dumps(data_dict)}\n\n"

                    elif kind in ("on_agent_finish", "on_chain_end"):
                        data = event.get("data", {})
                        final_output = data.get("output", {}) if isinstance(data, dict) else {}
                        final_messages = final_output.get("messages", []) if isinstance(final_output, dict) else []

                        logger.info(
                            f"RUN - final - messages count={len(final_messages)}; types={[type(m).__name__ for m in final_messages]}"
                        )

                        # Raccoglie ToolMessage prodotti nel run
                        try:
                            for m in final_messages:
                                if isinstance(m, ToolMessage):
                                    tool_records.append({
                                        "name": getattr(m, "name", None),
                                        "result": m.content,
                                    })
                        except Exception as e:
                            logger.warning(f"Tool extraction error: {e}")

                        # Ultimo contenuto assistente (se non già streammato)
                        if final_messages:
                            last_msg = final_messages[-1]
                            if isinstance(last_msg, AIMessage):
                                content_text = _extract_text(last_msg.content)
                                if content_text and not response_chunks:
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

            # Persistenza su DB a fine streaming
            response = "".join([c for c in response_chunks if c])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"RUN TERMINATA alle {timestamp}: response_len={len(response)} tool_records={len(tool_records)}")
            logger.info(f"\nRUN - Risposta:\n\n{response}")

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
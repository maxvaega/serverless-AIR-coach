import datetime
import json
from typing import AsyncGenerator, Optional, Union

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from .env import FORCED_MODEL, DATABASE_NAME, COLLECTION_NAME, HISTORY_LIMIT
from .database import get_data, insert_data
from .auth0 import get_user_metadata
from .utils import (
    format_user_metadata,
    _extract_text,
    get_combined_docs,
    build_system_prompt,
    ensure_prompt_initialized,
    get_prompt_with_version,
)
from .cache import get_cached_user_data, set_cached_user_data
from .tools import domanda_teoria, _serialize_tool_output
from .logging_config import logger
from .history_hooks import build_llm_input_window_hook
from .prompt_personalization import (
    get_personalized_prompt_for_user,
    generate_thread_id,
)


# ------------------------------------------------------------------------------
# Costanti e stato di modulo
# ------------------------------------------------------------------------------
combined_docs: str = ""
system_prompt: str = ""
llm: Optional[ChatGoogleGenerativeAI] = None  # non usare a livello globale in serverless
# Checkpointer globale riutilizzabile (non legato all'event loop) per mantenere memoria volatile tra richieste
checkpointer: Optional[InMemorySaver] = None
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
    tools = [domanda_teoria]
    local_checkpointer = _get_checkpointer()
    # Prompt personalizzato per utente e versione
    personalized_prompt, prompt_version, _ = get_personalized_prompt_for_user(
        user_id=user_id, token=token, fetch_user_data=user_data
    )
    agent_executor = create_react_agent(
        local_llm,
        tools,
        prompt=personalized_prompt,
        pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT),
        checkpointer=local_checkpointer,
    )

    # Branch non-stream (sync)
    if not stream:
        try:
            # Invocazione sincrona
            try:
                # Thread id versionato per utente
                config = {"configurable": {"thread_id": generate_thread_id(user_id, prompt_version), "recursion_limit": 2}}
                # Cold start: seed da DB se necessario
                state = None
                try:
                    state = agent_executor.get_state(config)
                except Exception:
                    pass
                existing = state.values.get("messages") if state and hasattr(state, "values") else None
                if not existing and chat_history:
                    seed_messages = []
                    try:
                        history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=HISTORY_LIMIT)
                        for msg in history:
                            if msg.get("human"):
                                seed_messages.append(HumanMessage(msg["human"]))
                            if msg.get("system"):
                                seed_messages.append(AIMessage(msg["system"]))
                    except Exception as e:
                        logger.error(f"HISTORY - Errore nel recuperare la chat history: {e}")
                    if seed_messages:
                        try:
                            agent_executor.update_state(config, {"messages": seed_messages})
                        except Exception as e:
                            logger.error(f"Error seeding agent state: {e}")

                result = agent_executor.invoke({"messages": [HumanMessage(query)]}, config=config)
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
            serialized_output = None

            # Best practice: thread per utente, versionato sul prompt per isolamento memoria tra versioni
            config = {"configurable": {"thread_id": generate_thread_id(str(user_id), prompt_version), "recursion_limit": 2}}

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
                logger.info("HISTORY - Nessun messaggio trovato in memoria volatile")
                seed_messages = []

                # Seed da DB se richiesto
                if chat_history:
                    logger.info("HISTORY - Cerco cronologia conversazione su DB...")
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
                            
                            if msg.get("system"):
                                seed_messages.append(AIMessage(msg["system"]))
                            
                            if tool_entry:
                                try:
                                    # Supporta sia schema vecchio (name/result) sia nuovo (tool_name/data) e anche lista di record
                                    entry = None
                                    if isinstance(tool_entry, list) and tool_entry:
                                        entry = tool_entry[-1]
                                    elif isinstance(tool_entry, dict):
                                        entry = tool_entry

                                    if isinstance(entry, dict):
                                        tool_name = entry.get("name") or entry.get("tool_name") or "unknown_tool"
                                        tool_result = entry.get("result") or entry.get("data")
                                    else:
                                        tool_name = "unknown_tool"
                                        tool_result = tool_entry

                                    if tool_result is None:
                                        logger.debug("HISTORY DEBUG - tool_result assente, salto creazione ToolMessage")
                                    else:
                                        content_str = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
                                        tool_message = ToolMessage(
                                            content=content_str,
                                            tool_call_id=f"call_{tool_name}_{msg.get('timestamp', 'unknown')}"
                                        )
                                        seed_messages.append(tool_message)
                                        # LOGGER DEBUG
                                        logger.info(
                                            f"HISTORY DEBUG - ToolMessage aggiunto al seeding: tool={tool_name}, content_len={len(content_str)}"
                                        )

                                except Exception as te:
                                    logger.error(f"Errore nella creazione del ToolMessage per il seeding: {te}")

                        if history:
                            logger.info(f"HISTORY - Cronologia recuperata da DB: {len(history)} messaggi")
                    except Exception as e:
                        logger.error(f"Errore nel recuperare la chat history: {e}")

                # Aggiorna memoria volatile (nessun trimming; pre_model_hook limiterà la finestra all'LLM)
                if seed_messages:
                    try:
                        agent_executor.update_state(config, {"messages": seed_messages})
                    except Exception as e:
                        logger.error(f"Error seeding agent state: {e}")
            else:
                # WARM PATH: nessun trimming; lo stato rimane completo
                logger.info("HISTORY - Memoria volatile presente (warm).")

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

                        # decommentare per inviare evento tool start al client
                        # start_message = {
                        #     "type": "tool_start",
                        #     "tool_name": tool_name,
                        #     "input": tool_input
                        # }
                        # yield f"data: {json.dumps(start_message)}\n\n" 
                        logger.info(f"TOOL - {tool_name} started with input: {tool_input}")

                    elif kind == "on_tool_end":
                        tool_executed = True
                        tool_name = event.get("name")
                        tool_data = event.get("data", {})
                        tool_output = tool_data.get("output")

                        if tool_output:
                            # Serializza correttamente l'output del tool
                            serialized_output = _serialize_tool_output(tool_output)

                            tool_record = {
                                "tool_name": tool_name,
                                "data": serialized_output
                            }
                            tool_records.append(tool_record)

                            structured_response = {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "data": serialized_output,
                                "final": True
                            }
                            yield f"data: {json.dumps(structured_response)}\n\n"
                            logger.info(f"TOOL - {tool_name} output processed")
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
                    logger.info(f"RUN - Risposta LLM:\n{response}")
                    if serialized_output is not None:
                        logger.info(f"RUN - Risposta Tool:\n{serialized_output}")

                    # Se l'agente non ha prodotto risposta e non ha chiamato alcun tool,
                    # invia uno spazio al frontend e registra un warning
                    if (not response or response == "") and (not tool_executed):
                        logger.warning("STREAM - Nessuna risposta dall'agente e nessun tool eseguito. Forzo uno spazio vuoto al client")
                        response = " "
                        fallback_ai_response = {
                            "type": "agent_message",
                            "data": response
                        }
                        # Invia un singolo spazio, formattato come gli altri chunk agent_message
                        yield f"data: {json.dumps(fallback_ai_response)}\n\n"

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
                        logger.info(f"DB - Risposta inserita nella collection: {DATABASE_NAME} - {COLLECTION_NAME} ")

                    #### DEBUG ##
                    # Log post-run: cronologia aggiornata nello stato del thread
                    # try:
                    #     state_after_run = agent_executor.get_state(config)
                    #     msgs_after = state_after_run.values.get("messages") if state_after_run and hasattr(state_after_run, "values") else []
                    #     total_msgs = len(msgs_after) if msgs_after else 0
                    #     human_msgs = sum(1 for m in (msgs_after or []) if isinstance(m, HumanMessage))
                    #     ai_msgs = sum(1 for m in (msgs_after or []) if isinstance(m, AIMessage))
                    #     tool_msgs = sum(1 for m in (msgs_after or []) if isinstance(m, ToolMessage))
                    #     logger.info(
                    #         f"HISTORY - Stato dopo run: total={total_msgs} human={human_msgs} ai={ai_msgs} tool={tool_msgs}"
                    #     )
                    #     # Dettaglio ultimi 10 messaggi per debug
                    #     tail = (msgs_after or [])[-10:]
                    #     def _shorten(txt: str, max_len: int = 120) -> str:
                    #         if txt is None:
                    #             return ""
                    #         return txt if len(txt) <= max_len else txt[:max_len] + "..."
                    #     details = []
                    #     for idx, m in enumerate(tail, start=max(0, total_msgs - len(tail))):
                    #         if isinstance(m, HumanMessage):
                    #             details.append(f"[{idx}] Human: {_shorten(m.content if isinstance(m.content, str) else str(m.content))}")
                    #         elif isinstance(m, AIMessage):
                    #             details.append(f"[{idx}] AI: {_shorten(m.content if isinstance(m.content, str) else str(m.content))}")
                    #         elif isinstance(m, ToolMessage):
                    #             details.append(f"[{idx}] Tool: {_shorten(m.content if isinstance(m.content, str) else str(m.content))}")
                    #         else:
                    #             details.append(f"[{idx}] {type(m).__name__}")
                    #     if details:
                    #         logger.debug("HISTORY DEBUG - Ultimi messaggi dopo run:\n" + "\n".join(details))
                    # except Exception as e_hist:
                    #     logger.error(f"HISTORY - Errore nel loggare lo stato dopo run: {e_hist}")
                        
                except Exception as e:
                    logger.error(f"DB - Errore nell'inserire i dati nella collection: {e}")

        return stream_response()


# Re-export per i test unitari
build_llm_input_window_hook = build_llm_input_window_hook
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk, ToolMessage
from .logging_config import logger
import datetime
from .env import *
import json
from .database import get_data, insert_data
from .auth0 import get_user_metadata
from .utils import format_user_metadata
from .cache import get_cached_user_data, set_cached_user_data
from .s3_utils import fetch_docs_from_s3, create_prompt_file
import threading
from .utils import get_combined_docs, update_docs_from_s3

# Import agent creation tools
from langgraph.prebuilt import create_react_agent
from .tools import test_licenza
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

import langchain
# from langchain_community.cache import InMemoryCache


def build_system_prompt(combined_docs: str) -> str:
    """
    Costruisce e restituisce il system_prompt utilizzando il contenuto combinato dei documenti.
    """
    return f"""{combined_docs}"""

def update_docs():
    """
    Wrapper function to update docs.
    Calls the core logic in utils.py and updates the global state of this module.
    """
    global combined_docs, system_prompt

    update_result = update_docs_from_s3()

    # Update global variables in this module
    if update_result and "system_prompt" in update_result:
        combined_docs = update_result["system_prompt"]
        system_prompt = build_system_prompt(combined_docs)
        logger.info("system prompt updated successfully.")

    return update_result

# Load Documents from S3 on load to build prompt
combined_docs = get_combined_docs()
system_prompt = build_system_prompt(combined_docs)

 # Structured output schema to guarantee a final step
class FinalAnswer(BaseModel):
    answer: str

STRUCTURED_PROMPT = (
    "Compose a concise, user-facing final answer based on the conversation and tool results. "
    "Do not include JSON or code unless strictly necessary."
)

# Define LLM Model
model = FORCED_MODEL
logger.info(f"Selected LLM model: {model}")
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    # cache=True,
)

# Define Tools and Agent
tools = [test_licenza]

# Best practice: pass prompt to prebuilt agent and enable volatile memory via checkpointer
checkpointer = InMemorySaver()
agent_executor = create_react_agent(
    llm,
    tools,
    prompt=system_prompt,
    # response_format=(STRUCTURED_PROMPT, FinalAnswer),
    checkpointer=checkpointer,
)

def ask(query, user_id, chat_history=False, stream=False, user_data: bool = False, token: str = None):
    """
    Processes a user query using a LangChain agent and returns a response, optionally streaming.
    The agent can decide to use tools available.
    Memory is handled by the checkpointer if available, otherwise by fetching history from MongoDB.
    User profile metadata is fetched from auth0 if requested.
    """
    # messages = [SystemMessage(system_prompt)]
    user_info = None
    messages = []

    if not stream:
        try:
            if user_data:
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
            return f"data: {{'error': 'Errore nel recuperare i dati dell\'utente: {str(e)}'}}\n\n"
        
        # NOTE: Manual chat history management
        history_limit = 10
        try:
            if chat_history:
                history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=history_limit)
                for msg in history:
                    messages.append(HumanMessage(msg["human"]))
                    messages.append(AIMessage(msg["system"]))
                    logger.info(f"Chat history: {msg['human']} \n-> \n{msg['system']}")
        except Exception as e:
            logger.error(f"Errore nel recuperare la chat history: {e}")
            return f"data: {{'error': 'Errore nel recuperare la chat history: {str(e)}'}}\n\n"

        # Append the current user query
        messages.append(HumanMessage(query))

        # Synchronous invocation (not the primary use case for this app)
        try:
            result = agent_executor.invoke({"messages": messages})
            # The final response is in the 'messages' list, typically the last one.
            final_response = result['messages'][-1].content
            return final_response
        except Exception as e:
            logger.error(f"Errore nell'invocare l'agente: {e}")
            return "Errore nell'invocare l'agente."

    else:
        # Asynchronous streaming invocation
        response_chunks = []

        async def stream_response():
            # Best practice config with thread_id for per-user thread
            config = {"configurable": {"thread_id": str(user_id)}}

            # Hybrid memory: prefer volatile memory if present; otherwise seed from DB
            try:
                state = agent_executor.get_state(config)
                existing_messages = state.values.get("messages") if state and hasattr(state, "values") else None
                msg_count = len(existing_messages) if existing_messages else 0
                logger.info(f"Recupero lo stato dell'agente. Numero di messaggi trovati in memoria: {msg_count}")
            except Exception as e:
                logger.error(f"Errore nel recuperare lo stato dell'agente: {e}")
                existing_messages = None

            if not existing_messages:
                logger.info("Nessun messaggio trovato in memoria, carico cronologia conversazione da DB...")
                seed_messages = []
                # Cold start: inject user info into volatile memory (not persisted to DB)
                if user_data:
                    try:
                        ui = get_cached_user_data(user_id)
                        if not ui:
                            user_metadata = get_user_metadata(user_id, token=token)
                            ui = format_user_metadata(user_metadata)
                            if ui:
                                set_cached_user_data(user_id, ui)
                        if ui:
                            # Inject as AIMessage in short-term memory only
                            seed_messages.append(AIMessage(ui))
                            logger.info("User info inserito nella memoria volatile del thread (cold start)")
                    except Exception as e:
                        logger.error(f"Errore nel recuperare i dati utente per cold start: {e}")

                # Optionally hydrate from DB if requested
                if chat_history:
                    try:
                        history_limit = 10
                        history = get_data(
                            DATABASE_NAME,
                            COLLECTION_NAME,
                            filters={"userId": user_id},
                            limit=history_limit,
                        )
                        for msg in history:
                            # Human question
                            if msg.get("human"):
                                seed_messages.append(HumanMessage(msg["human"]))
                            # Historic tool result (if stored previously)
                            tool_entry = msg.get("tool")
                            if tool_entry:
                                try:
                                    # Provide tool result as AI message for context (avoid SystemMessage in state)
                                    tool_name = tool_entry.get("name") if isinstance(tool_entry, dict) else None
                                    tool_payload = tool_entry.get("result") if isinstance(tool_entry, dict) else tool_entry
                                    tool_text = json.dumps(tool_payload) if not isinstance(tool_payload, str) else tool_payload
                                    seed_messages.append(AIMessage(f"previous tool [{tool_name}] result : \n{tool_text}"))
                                except Exception:
                                    # Fallback: ignore malformed tool payloads
                                    pass
                            # Assistant answer
                            if msg.get("system"):
                                seed_messages.append(AIMessage(msg["system"]))
                    except Exception as e:
                        logger.error(f"Errore nel recuperare la chat history: {e}")

                # Seed volatile memory only if we actually have messages
                if seed_messages:
                    try:
                        agent_executor.update_state(config, {"messages": seed_messages})
                        logger.info(f"MEMORY: stato dell'agente aggiornato con {len(seed_messages)} messaggi recuperati dal DB")
                    except Exception as e:
                        logger.error(f"Error seeding agent state: {e}")

            # Track tool outputs produced during this run
            tool_records = []

            # Helper: normalize AI message content to text
            def _extract_text(content) -> str:
                try:
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        # Anthropic-style parts: [{'type':'text','text':'...'}, ...]
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

            try:
                # Stream only the current user message; memory is already in the thread state
                async for event in agent_executor.astream_events(
                    {"messages": [HumanMessage(query)]},
                    config=config,
                    version="v2",
                ):
                    kind = event.get("event")
                    # logger.info(f"EVENT kind={kind} name={event.get('name')} path={event.get('run_id')}")

                    if kind == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if isinstance(chunk, AIMessageChunk):
                            content_text = _extract_text(chunk.content)
                            if content_text:
                                response_chunks.append(content_text)
                                data_dict = {"data": content_text}
                                yield f"data: {json.dumps(data_dict)}\n\n"
                                logger.debug(f"Streamed chunk size={len(content_text)}")

                    # Capture final output on both on_agent_finish and on_chain_end to be robust across providers
                    elif kind in ("on_agent_finish", "on_chain_end"):
                        data = event.get("data", {})
                        final_output = data.get("output", {}) if isinstance(data, dict) else {}
                        final_messages = final_output.get("messages", []) if isinstance(final_output, dict) else []

                        logger.info(
                            f"FINAL messages count={len(final_messages)}; types={[type(m).__name__ for m in final_messages]}"
                        )

                        # Collect any tool messages from this run
                        try:
                            for m in final_messages:
                                if isinstance(m, ToolMessage):
                                    tool_records.append({
                                        "name": getattr(m, "name", None),
                                        "result": m.content,
                                    })
                        except Exception as e:
                            logger.warning(f"Tool extraction error: {e}")

                        # Capture final assistant content if present
                        if final_messages:
                            last_msg = final_messages[-1]
                            if isinstance(last_msg, AIMessage):
                                content_text = _extract_text(last_msg.content)
                                if content_text and not response_chunks:  # Yield only if not already streamed
                                    response_chunks.append(content_text)
                                    yield f"data: {json.dumps({'data': content_text})}\n\n"

            except Exception as e:
                logger.error(f"Errore nello streaming della risposta dell'agente: {e}")
                yield f"data: {{'error': 'Errore nello streaming della risposta dell\'agente: {str(e)}'}}\n\n"

            # Fallback: if no text was streamed nor final text captured but we have tool results,
            # emit the last tool result as response to avoid empty output
            if not response_chunks and tool_records:
                try:
                    last_tool = tool_records[-1]
                    tool_result = last_tool.get("result")
                    tool_text = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
                    if tool_text:
                        yield f"data: {json.dumps({'data': tool_text})}\n\n"
                        response_chunks.append(tool_text)
                        logger.info("Fallback response emitted from tool result due to empty assistant output")
                except Exception as e:
                    logger.warning(f"Fallback from tool failed: {e}")

            # After streaming, save the complete response to DB
            response = "".join([c for c in response_chunks if c])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"RUN TERMINATA alle {timestamp}: response_len={len(response)} tool_records={len(tool_records)}")
            logger.info(f"Risposta: {response}")

            try:
                data = {
                    "human": query,
                    "system": response,
                    "userId": user_id,
                    "timestamp": timestamp,
                }
                if tool_records:
                    # Salva solo l'ultimo elemento di tool_records
                    data["tool"] = tool_records[-1]
                if response or data.get("tool"):  # Inserisce solo se la risposta non è vuota e/o se c'è un valore tool
                    insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                    logger.info(f"Risposta inserita nella collection: {COLLECTION_NAME} ")
            except Exception as e:
                logger.error(f"Errore nell'inserire i dati nella collection: {e}")
                # Do not yield error to client here as the stream is already closed

        return stream_response()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk
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
from .tools import test_licenza, reperire_documentazione_air_coach


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
        logger.info("RAG module state updated successfully.")

    return update_result

# Load Documents from S3 on load to build prompt
combined_docs = get_combined_docs()
system_prompt = build_system_prompt(combined_docs)

# Define LLM Model
model = FORCED_MODEL
logger.info(f"Selected LLM model: {model}")
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    cache=True,
)

# Define Tools and Agent
tools = [test_licenza, reperire_documentazione_air_coach]
agent_executor = create_react_agent(llm, tools)

def ask(query, user_id, chat_history=False, stream=False, user_data: bool = False, token: str = None):
    """
    Processes a user query using a LangChain agent and returns a response, optionally streaming.
    The agent can decide to use tools like `test_licenza` or `reperire_documentazione_air_coach`.
    Memory is handled manually by fetching history from MongoDB.
    """
    # NOTE: The system prompt is handled by including it in the messages list.
    # The agent will receive it as the first message.
    messages = [SystemMessage(system_prompt)]

    # NOTE: User data retrieval logic is preserved as per instructions.
    try:
        if user_data:
            user_info = get_cached_user_data(user_id)
            if not user_info:
                user_metadata = get_user_metadata(user_id, token=token)
                user_info = format_user_metadata(user_metadata)
                set_cached_user_data(user_id, user_info)
            if user_info:
                messages.append(AIMessage(user_info))
    except Exception as e:
        logger.error(f"An error occurred while retrieving user data for user ID {user_id}: {e}")
        return f"data: {{'error': 'An error occurred while retrieving user data: {str(e)}'}}\n\n"
    
    # NOTE: Manual chat history management is preserved as per instructions.
    history_limit = 10
    try:
        if chat_history:
            history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=history_limit)
            for msg in history:
                messages.append(HumanMessage(msg["human"]))
                messages.append(AIMessage(msg["system"]))
    except Exception as e:
        logger.error(f"An error occurred while retrieving chat history: {e}")
        return f"data: {{'error': 'An error occurred while retrieving chat history: {str(e)}'}}\n\n"

    # Append the current user query
    messages.append(HumanMessage(query))

    if not stream:
        # Synchronous invocation (not the primary use case for this app)
        try:
            result = agent_executor.invoke({"messages": messages})
            # The final response is in the 'messages' list, typically the last one.
            final_response = result['messages'][-1].content
            return final_response
        except Exception as e:
            logger.error(f"An error occurred during agent invocation: {e}")
            return "An error occurred while processing your request."

    else:
        # Asynchronous streaming invocation
        response_chunks = []

        async def stream_response():
            try:
                # The agent stream yields a sequence of events (dicts)
                # We are interested in the AI message chunks
                async for event in agent_executor.astream_events({"messages": messages}, version="v2"):
                    kind = event["event"]
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if isinstance(chunk, AIMessageChunk):
                            content = chunk.content
                            if content:
                                response_chunks.append(content)
                                data_dict = {"data": content}
                                data_json = json.dumps(data_dict)
                                yield f"data: {data_json}\n\n"
                                logger.debug(f"Streamed chunk: {content}")

            except Exception as e:
                logger.error(f"An error occurred while streaming the agent response: {e}")
                yield f"data: {{'error': 'An error occurred while streaming the response: {str(e)}'}}\n\n"
            
            # After streaming, save the complete response to DB
            response = "".join(response_chunks)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Response completed at {timestamp}: {response}")

            try:
                data = {
                    "human": query,
                    "system": response,
                    "userId": user_id,
                    "timestamp": timestamp
                }
                if response: # Only insert if the response is not empty
                    insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                    logger.info(f"Response inserted into the collection: {COLLECTION_NAME} ")
            except Exception as e:
                logger.error(f"An error occurred while inserting data into the collection: {e}")
                # Do not yield error to client here as the stream is already closed

        return stream_response()

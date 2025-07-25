from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from .logging_config import logger
import datetime
from .env import *
import json
from .database import get_data
from .auth0 import get_user_metadata
from .utils import format_user_metadata
from .cache import get_cached_user_data, set_cached_user_data
from .s3_utils import get_combined_docs, build_system_prompt, update_docs
from .tools import AVAILABLE_TOOLS
import threading

_docs_cache = {
    "content": None,
    "docs_meta": None,
    "timestamp": None 
}
update_docs_lock = threading.Lock()  # Lock per sincronizzare gli aggiornamenti manuali

# Load Documents from S3 on load to build prompt
combined_docs = get_combined_docs()
system_prompt = build_system_prompt(combined_docs)

# Define LLM Model
model = "gemini-2.5-flash-lite-preview-06-17" # test only, rimettere "gemini-2.5-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    cache=True,
)

tool_name = "domanda_quiz_teoria"
tools = []
for tool_name, tool in AVAILABLE_TOOLS.items():
    tools.append(tool)

agent_graph = create_react_agent(
        model=llm, 
        tools=tools,
        prompt=system_prompt
)

logger.info(f"Agent Graph created with model: {model} and tools: {', '.join([tool.name for tool in tools])}")

def ask(query, user_id, chat_history=False, stream=False, user_data: bool = False, token: str = None):
    """
    Processes a user query and returns a response, optionally streaming the response.

    This function uses a combination of retrieval and chain mechanisms to process the query
    and generates a response. If chat history is provided, it extends the messages with the
    chat history and appends the new query. The function supports both synchronous and
    asynchronous streaming of responses. In streaming mode, it yields chunks of data and
    inserts the final response into a MongoDB collection.

    :param query: The user query to process.
    :param user_id: The ID of the user making the query.
    :param chat_history: Optional; A list of previous chat messages to include in the context.
    :param stream: Optional; If True, streams the response asynchronously.
    :return: The response to the query, either as a single result or a generator for streaming.
    """
    messages = []
    
    if user_data:
        # Recupera i dati utente dalla cache
        user_info = get_cached_user_data(user_id)
        if not user_info:
            # Recupera i metadata da Auth0
            user_metadata = get_user_metadata(user_id, token=token)
            user_info = format_user_metadata(user_metadata)
            set_cached_user_data(user_id, user_info)
        if user_info:
            messages.append({
                "role": "system",
                "content": user_info
            })
            logger.info(f"User info for {user_id} added to messages: \n")
    
    history_limit = 10
    if chat_history:
        history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=history_limit)
        for msg in history:
            messages.append({"role": "user", "content": msg["human"]})
            messages.append({"role": "assistant", "content": msg["system"]})
        logger.info(f"Chat history for user {user_id} loaded with {len(history)} messages.")

    messages.append({"role": "user", "content": query})

    logger.info(messages)
    
    if not stream:
        return agent_graph.invoke(messages)
    else:
        from .database import insert_data
        response_chunks = []

        async def stream_response():
            for event in agent_graph.stream(messages):
                try:
                    content = event.content
                    response_chunks.append(content)
                    data_dict = {"data": content}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"
                except Exception as e:
                    logger.error(f"An error occurred while streaming the events: {e}")
            # Insert the data into the MongoDB collection
            response = "".join(response_chunks)
            try:
                data = {
                    "human": query,
                    "system": response,
                    "userId": user_id,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                logger.info(f"Data inserted into the collection: {COLLECTION_NAME}")
            except Exception as e:
                logger.error(f"An error occurred while inserting the data into the collection: {e}")
        return stream_response()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
logger = logging.getLogger("uvicorn")
import datetime
from app.config import settings
import json
from .database import get_data, insert_data
from .auth0 import get_user_metadata
from .utils import format_user_metadata
from .cache import get_cached_user_data, set_cached_user_data
from .s3_utils import fetch_docs_from_s3, create_prompt_file
import threading

_docs_cache = {
    "content": None,
    "docs_meta": None,
    "timestamp": None 
}
update_docs_lock = threading.Lock()  # Lock per sincronizzare gli aggiornamenti manuali

def get_combined_docs():
    """
    Restituisce il contenuto combinato dei file Markdown usando la cache se disponibile.
    Aggiorna anche i metadati se la cache è vuota.
    """
    global _docs_cache
    if (_docs_cache["content"] is None) or (_docs_cache["docs_meta"] is None):
        logger.info("Docs: cache is empty. Fetching from S3...")
        now = datetime.datetime.utcnow()
        result = fetch_docs_from_s3()
        _docs_cache["content"] = result["combined_docs"]
        _docs_cache["docs_meta"] = result["docs_meta"]
        _docs_cache["timestamp"] = now
    else:
        logger.info("Docs: found valid cache in use. no update triggered.")
    return _docs_cache["content"]

def build_system_prompt(combined_docs: str) -> str:
    """
    Costruisce e restituisce il system_prompt utilizzando il contenuto combinato dei documenti.
    """
    return f"""{combined_docs}"""

def update_docs():
    """
    Forza l'aggiornamento della cache dei documenti da S3 e rigenera il system_prompt.
    Aggiorna anche i metadati dei file e restituisce, nella response, il numero di documenti e per ognuno:
    il titolo e la data di ultima modifica.
    """
    global _docs_cache, combined_docs, system_prompt
    with update_docs_lock:
        logger.info("Docs: manual update in progress...")
        now = datetime.datetime.utcnow()
        result = fetch_docs_from_s3()
        _docs_cache["content"] = result["combined_docs"]
        _docs_cache["docs_meta"] = result["docs_meta"]
        _docs_cache["timestamp"] = now
        combined_docs = _docs_cache["content"]
        system_prompt = build_system_prompt(combined_docs)
        logger.info("Docs Cache and system_prompt updated successfully.")

        # Prepara i dati da ritornare: numero di documenti e metadati
        docs_count = len(result["docs_meta"])
        docs_details = result["docs_meta"]

        return {
            "message": "Document cache and system prompt updated successfully.",
            "docs_count": docs_count,
            "docs_details": docs_details,
            "system_prompt": system_prompt
        }

# Load Documents from S3 on load to build prompt
combined_docs = get_combined_docs()
system_prompt = build_system_prompt(combined_docs)

# Define LLM Model
model = settings.FORCED_MODEL
logger.info(f"Selected LLM model: {model}")
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=0.7,
    cache=True,
)

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
    messages = [SystemMessage(system_prompt)]
    try:
        if user_data:
            # Recupera i dati utente dalla cache
            user_info = get_cached_user_data(user_id)
            if not user_info:
                # Recupera i metadata da Auth0
                user_metadata = get_user_metadata(user_id, token=token)
                user_info = format_user_metadata(user_metadata)
                set_cached_user_data(user_id, user_info)
            if user_info:
                messages.append(AIMessage(user_info))
    except Exception as e:
        logger.error(f"An error occurred while retrieving user data: {e}")
        return f"data: {{'error': 'An error occurred while retrieving user data: {str(e)}'}}\n\n"
    
    history_limit = 10

    try:
        if chat_history:
            history = get_data(settings.DATABASE_NAME, settings.COLLECTION_NAME, filters={"userId": user_id}, limit=history_limit)
            for msg in history:
                messages.append(HumanMessage(msg["human"]))
                messages.append(AIMessage(msg["system"]))
        messages.append(HumanMessage(query))

    except Exception as e:
        logger.error(f"An error occurred while retrieving chat history: {e}")
        return f"data: {{'error': 'An error occurred while retrieving chat history: {str(e)}'}}\n\n"

    if not stream:
        return llm.invoke(messages)
    else:
        response_chunks = []

        async def stream_response():
            try:
                for event in llm.stream(input=messages):
                    content = event.content
                    response_chunks.append(content)
                    data_dict = {"data": content}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"
                    logger.info(f"event= {event}")
            except Exception as e:
                logger.error(f"An error occurred while streaming the response: {e}")
                yield f"data: {{'error': 'An error occurred while streaming the response: {str(e)}'}}\n\n"
            # Insert the data into the MongoDB collection
            
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
                insert_data(settings.DATABASE_NAME, settings.COLLECTION_NAME, data)
                logger.info(f"Response inserted into the collection: {settings.COLLECTION_NAME} ")
            except Exception as e:
                logger.error(f"An error occurred while inserting the data into the collection: {e}")
                yield f"data: {{'error': 'An error occurred while inserting the data into the collection: {str(e)}'}}\n\n"
        return stream_response()

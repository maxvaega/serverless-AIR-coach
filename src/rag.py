from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .logging_config import logger
import datetime
from .env import *
import json
from .database import get_data #, ensure_indexes
import boto3
import threading

from .auth0 import get_user_metadata
from .utils import format_user_metadata
from .cache import get_cached_user_data, set_cached_user_data
from typing import Optional

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
_docs_cache = {
    "content": None,
    "docs_meta": None,
    "timestamp": None 
}
update_docs_lock = threading.Lock()  # Lock per sincronizzare gli aggiornamenti manuali

def fetch_docs_from_s3():
    """
    Downloads Markdown files from the S3 bucket, combines their content and retrieves file metadata.
    Restituisce un dizionario con:
      - "combined_docs": contenuto combinato dei file (per system_prompt)
      - "docs_meta": lista di dizionari con "title" e "last_modified" per ogni file
    """
    try:
        objects = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='docs/')
        docs_content = []
        docs_meta = []

        # Itera sugli oggetti nel bucket
        for obj in objects.get('Contents', []):
            if obj['Key'].endswith('.md'):  # Filtra solo i file Markdown
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                file_content = response['Body'].read().decode('utf-8')
                docs_content.append(file_content)
                # Estrae il titolo dal nome del file (l'ultima parte del key)
                title = obj['Key'].split('/')[-1]
                # Formatta la data/ora di ultima modifica
                last_modified = obj.get('LastModified')
                if isinstance(last_modified, datetime.datetime):
                    last_modified = last_modified.strftime("%Y-%m-%d %H:%M:%S")
                docs_meta.append({
                    "title": title,
                    "last_modified": last_modified
                })

        combined_docs = "\n\n".join(docs_content)
        logger.info(f"Docs: Found and loaded {len(docs_content)} Markdown files from S3.")
        return {"combined_docs": combined_docs, "docs_meta": docs_meta}

    except Exception as e:
        logger.error(f"Error while downloading files from S3: {e}")
        return {"combined_docs": "", "docs_meta": []}

def get_combined_docs():
    """
    Returns the combined content of the Markdown files using the cache if available.
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
model = "gemini-2.0-flash"
llm = ChatGoogleGenerativeAI(
    model=model,
    temperature=1,
)

# ensure_indexes(DATABASE_NAME, COLLECTION_NAME)

def ask(query, user_id, chat_history=False, stream=False, user_data: bool = False):
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
    
    if user_data:
        # Recupera i dati utente dalla cache
        user_info = get_cached_user_data(user_id)
        # logger.info(f"user_info: {user_info}")
        if not user_info:
            # Recupera i metadata da Auth0
            user_metadata = get_user_metadata(user_id)
            # logger.info(f"user_metadata: {user_metadata}")
            # Formatta i metadata
            user_info = format_user_metadata(user_metadata)
            # Salva nella cache
            set_cached_user_data(user_id, user_info)
        if user_info:
            messages.append(AIMessage(user_info))
    
    history_limit = 10
    if chat_history:
        history = get_data(DATABASE_NAME, COLLECTION_NAME, filters={"userId": user_id}, limit=history_limit)
        for msg in history:
            messages.append(HumanMessage(msg["human"]))
            messages.append(AIMessage(msg["system"]))

    messages.append(HumanMessage(query))

    if not stream:
        return llm.invoke(messages)
    else:
        from .database import insert_data
        response_chunks = []

        async def stream_response():
            for event in llm.stream(input=messages):
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
                    "llm": model,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                insert_data(DATABASE_NAME, COLLECTION_NAME, data)
                logger.info(f"Data inserted into the collection: {COLLECTION_NAME}")
            except Exception as e:
                logger.error(f"An error occurred while inserting the data into the collection: {e}")
        return stream_response()

def create_prompt_file(system_prompt: str):
    """
    Creates a prompt file with the given system prompt.

    :param system_prompt: The system prompt to write to the file in AWS S3
    """
    s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    s3_key = "docs/system_prompt.md"

    try:
        file = s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=system_prompt,
            ContentType='text/markdown'
        )
        logger.info(f"System prompt salvato con successo in S3: s3://{BUCKET_NAME}/{s3_key}")
        return file
    except Exception as s3_error:
        logger.error(f"Errore nel salvare su S3: {str(s3_error)}")
        # Decidi se vuoi gestire l'errore S3 in modo specifico o lasciare che venga catturato
        # dal try/except esterno
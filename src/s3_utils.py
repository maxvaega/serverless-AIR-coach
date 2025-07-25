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
import boto3
import datetime
from .env import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME
from .logging_config import logger

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def fetch_docs_from_s3():
    """
    Scarica i file Markdown dal bucket S3, combina il contenuto e recupera i metadati dei file.
    Restituisce un dizionario con:
      - "combined_docs": contenuto combinato dei file (per system_prompt)
      - "docs_meta": lista di dizionari con "title" e "last_modified" per ogni file
    """
    try:
        objects = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='docs/')
        docs_content = []
        docs_meta = []

        for obj in objects.get('Contents', []):
            if obj['Key'].endswith('.md'):
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                file_content = response['Body'].read().decode('utf-8')
                docs_content.append(file_content)
                title = obj['Key'].split('/')[-1]
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

def create_prompt_file(system_prompt: str):
    """
    Crea un file di prompt con il system prompt fornito e lo salva su S3.
    """
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
        return None

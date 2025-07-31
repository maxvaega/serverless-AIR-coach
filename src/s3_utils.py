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
    s3_key = "prompt/system_prompt.md"
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

from .utils import update_prompt_from_s3
from .logging_config import logger

def update_docs():
    """
    Aggiorna i documenti su S3, ricostruisce e imposta il system prompt process-global
    tramite PromptManager, incrementando la versione.

    Ritorna un dict con message, docs_count, docs_details, system_prompt (finale), combined_docs e prompt_version.
    """
    try:
        result = update_prompt_from_s3()
        logger.info("Update docs: system prompt aggiornato e versione incrementata.")
        return result
    except Exception as e:
        logger.error(f"Update docs: errore durante l'aggiornamento del prompt: {e}")
        # Per coerenza, rilanciamo: l'endpoint gestirà l'HTTP 500
        raise
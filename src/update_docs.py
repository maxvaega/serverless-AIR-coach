from .utils import update_docs_from_s3, build_system_prompt
from .logging_config import logger

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
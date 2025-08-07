from typing import Dict
import datetime
import re
from .logging_config import logger
import threading
from .s3_utils import fetch_docs_from_s3

def format_user_metadata(user_metadata: Dict) -> str:
    """
    Formatta i metadata dell'utente in una stringa leggibile.

    :param user_metadata: Dizionario contenente i metadata dell'utente.
    :return: Stringa formattata con le informazioni dell'utente.
    """
    try:
        if not user_metadata:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            if date:
                formatted_data = f"\nOggi è il {date}\n"

            logger.info("Nessun metadata utente trovato.")
            return formatted_data
        
        formatted_data = "I dati che l’utente ti ha fornito su di sè sono:\n"
        
        # Date of Birth
        date_of_birth = user_metadata.get("date_of_birth")
        if date_of_birth:
            formatted_data += f"Data di Nascita: {date_of_birth}\n"
        
        # Jumps
        jumps = user_metadata.get("jumps")
        if jumps:
            jumps_mapping = {
                "0_10": "0 - 10",
                "11_50": "11 - 50",
                "51_150": "51 - 150",
                "151_300": "151 - 300",
                "301_1000": "301 - 1000",
                "1000+": "1000+"
            }
            if jumps in jumps_mapping:
                formatted_data += f"Numero di salti: {jumps_mapping[jumps]}\n"
            else:
                logger.warning(f"User metadata: Numero di salti non riconosciuto: {jumps}")
        
        # Preferred Dropzone
        preferred_dropzone = user_metadata.get("preferred_dropzone")
        if preferred_dropzone:
            formatted_data += f"Dropzone preferita: {preferred_dropzone}\n"
        
        # Qualifications
        qualifications = user_metadata.get("qualifications")
        if qualifications:
                qualifications_mapping = {
                "NO_PARACADUTISMO": "non ha mai fatto paracadutismo",
                "ALLIEVO": "allievo senza licenza",
                "LICENZIATO": "qualifica: Paracadutista licenziato",
                "DL": "qualifica: possiede la licenza di paracadutismo e la qualifica Direttore di lancio",
                "IP": "qualifica: possiede la qualifica da Istruttore di paracadutismo",
                }
                qualifica_formattata = qualifications_mapping.get(qualifications, "")

                if qualifica_formattata:
                    formatted_data += f"{qualifica_formattata}\n"
                else:
                    logger.warning(f"User metadata: Qualifica non riconosciuta: {qualifications}")

        # Name
        name = user_metadata.get("name")
        if name:
            formatted_data += f"Nome: {name}\n"
        
        # Surname
        surname = user_metadata.get("surname")
        if surname:
            formatted_data += f"Cognome: {surname}\n"
        
        # Sex
        sex = user_metadata.get("sex")
        if sex:
            sex_mapping = {
                "MASCHIO": "Maschio",
                "FEMMINA": "Femmina",
                "SCONOSCIUTO": "Preferisce non dirlo",
            }
            sesso_formattato = sex_mapping.get(sex, "")

            if sesso_formattato:
                formatted_data += f"Sesso: {sesso_formattato}\n"
            else:
                logger.warning(f"User metadata: Sesso non riconosciuto: {sex}")
        

        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date:
            formatted_data += f"\nOggi è il {date}\n"

        name = user_metadata.get("name")
        surname = user_metadata.get("surname")
        logger.info(f"New user metadata in cache: {name} {surname}\n{formatted_data}")

        return formatted_data
    
    except Exception as e:
        logger.error(f"An error occurred while formatting user metadata: {e}")
        return

# controlli per autenticazione user_id
def validate_user_id(user_id):
    # Regex per auth0
    auth0_pattern = r'^auth0\|[0-9a-fA-F]{24}$'

    # Regex per google-oauth2
    google_pattern = r'^google-oauth2\|[0-9]{15,25}$'

    # Controlla se il campo corrisponde a uno dei due pattern
    if re.match(auth0_pattern, user_id):
        return True
    elif re.match(google_pattern, user_id):
        return True
    else:
        return False

_docs_cache = {
    "content": None,
    "docs_meta": None,
    "timestamp": None
}
update_docs_lock = threading.Lock()

def get_combined_docs():
    """
    Restituisce il contenuto combinato dei file Markdown usando la cache se disponibile.
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

def update_docs_from_s3():
    """
    Forza l'aggiornamento della cache dei documenti da S3.
    Questa funzione aggiorna la cache `_docs_cache` e restituisce i dati aggiornati.
    """
    with update_docs_lock:
        logger.info("Docs: manual update in progress...")
        now = datetime.datetime.utcnow()
        result = fetch_docs_from_s3()
        _docs_cache["content"] = result["combined_docs"]
        _docs_cache["docs_meta"] = result["docs_meta"]
        _docs_cache["timestamp"] = now
        logger.info("Docs Cache updated successfully.")

        # Prepara i dati da ritornare
        docs_count = len(result["docs_meta"])
        docs_details = result["docs_meta"]

        # Costruisce un system_prompt temporaneo da ritornare, non modifica variabili globali
        system_prompt = result["combined_docs"]

        return {
            "message": "Document cache and system prompt updated successfully.",
            "docs_count": docs_count,
            "docs_details": docs_details,
            "system_prompt": system_prompt
        }
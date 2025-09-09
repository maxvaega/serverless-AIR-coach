from typing import Dict
import datetime
import re
import logging
logger = logging.getLogger("uvicorn")
import threading
from .s3_utils import fetch_docs_from_s3
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

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

            logger.info("USER INFO - Nessun metadata utente trovato.")
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
                logger.warning(f"USER INFO - Numero di salti non riconosciuto: {jumps}")
        
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
                    logger.warning(f"USER INFO - Qualifica non riconosciuta: {qualifications}")

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
                logger.warning(f"USER INFO - Sesso non riconosciuto: {sex}")
        

        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date:
            formatted_data += f"\nOggi è il {date}\n"

        name = user_metadata.get("name")
        surname = user_metadata.get("surname")
        logger.info(f"USER INFO - medatati salvati in cache per: {name} {surname}")

        return formatted_data
    
    except Exception as e:
        logger.error(f"USER INFO - Errore nel formattare i metadata utente: {e}")
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

# ----------------------------------------------------------------------------
# PromptManager (process-global) con versioning
# ----------------------------------------------------------------------------
_prompt_lock = threading.Lock()
_current_system_prompt: str | None = None
_prompt_version: int = 0

def get_prompt() -> str:
    global _current_system_prompt
    return _current_system_prompt or ""

def get_prompt_with_version() -> tuple[str, int]:
    global _current_system_prompt, _prompt_version
    return (get_prompt(), _prompt_version)

def ensure_prompt_initialized() -> None:
    """
    Inizializza il system prompt process-global se non presente usando la cache docs.
    Non effettua I/O se la cache è già popolata; altrimenti scarica da S3 via get_combined_docs().
    """
    global _current_system_prompt, _prompt_version
    if _current_system_prompt:
        return
    with _prompt_lock:
        if _current_system_prompt:
            return
        try:
            docs = get_combined_docs()
            _current_system_prompt = build_system_prompt(docs)
            # Prima inizializzazione: versione 1
            _prompt_version = 1
            logger.info("PromptManager: system prompt inizializzato dalla cache docs (v1).")
        except Exception as e:
            logger.error(f"PromptManager: errore durante inizializzazione del prompt: {e}")

def update_prompt_from_s3() -> dict:
    """
    Forza l'aggiornamento dei documenti da S3, ricostruisce il system prompt e
    aggiorna il PromptManager incrementando la versione.

    Ritorna un dict con message, docs_count, docs_details, system_prompt (finale).
    """
    global _current_system_prompt, _prompt_version
    with _prompt_lock:
        # Aggiorna la cache docs e ottieni combined_docs + meta
        update = update_docs_from_s3()
        # Back-compat: la funzione ritorna un campo "system_prompt" che è in realtà combined_docs
        combined_docs = update.get("combined_docs") or update.get("system_prompt") or ""
        # Costruisci il vero system prompt
        new_prompt = build_system_prompt(combined_docs)
        _current_system_prompt = new_prompt
        _prompt_version = (_prompt_version or 0) + 1
        logger.info(f"PromptManager: system prompt aggiornato (v{_prompt_version}).")
        return {
            "message": update.get("message", "Document cache and system prompt updated successfully."),
            "docs_count": update.get("docs_count", 0),
            "docs_details": update.get("docs_details", []),
            # Ritorniamo il vero system prompt finale
            "system_prompt": new_prompt,
            # E per completezza, anche il combined_docs
            "combined_docs": combined_docs,
            "prompt_version": _prompt_version,
        }

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

        # Back-compat: manteniamo il campo legacy "system_prompt" per i consumer esistenti,
        # ma ora aggiungiamo anche "combined_docs" esplicito.
        system_prompt_legacy = result["combined_docs"]

        return {
            "message": "Document cache and system prompt updated successfully.",
            "docs_count": docs_count,
            "docs_details": docs_details,
            "system_prompt": system_prompt_legacy,
            "combined_docs": result["combined_docs"],
        }

def build_system_prompt(docs: str) -> str:
    """
    Costruisce e restituisce il system_prompt utilizzando il contenuto combinato dei documenti.
    """
    return f"{docs}"


def _extract_text(content) -> str:
    """
    Normalizza il contenuto dei messaggi AI in stringa.
    """
    try:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
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


def trim_agent_messages(messages: list, history_limit: int) -> list:
    """
    Riduce i messaggi in memoria calda mantenendo solo gli ultimi `history_limit` turni
    (dove un turno inizia con un HumanMessage e può includere 0..n ToolMessage e 0..1 AIMessage).

    Regola speciale: se immediatamente prima del primo HumanMessage conservato c'è un AIMessage
    (es. messaggio-profilo utente seedato durante cold start), viene preservato.

    :param messages: Lista di messaggi nello stato volatile dell'agente.
    :param history_limit: Numero massimo di turni (HumanMessage) da mantenere.
    :return: Lista di messaggi eventualmente trimmata.
    """
    try:
        if not messages:
            logger.debug("TRIM - Nessun messaggio presente, nessuna azione.")
            return messages

        # Robustezza: forza history_limit a intero positivo
        try:
            history_limit = int(history_limit)
        except Exception:
            history_limit = 0

        if history_limit <= 0:
            logger.info("TRIM - history_limit non positivo: svuoto i messaggi.")
            return []

        human_indices = [idx for idx, m in enumerate(messages) if isinstance(m, HumanMessage)]
        human_count = len(human_indices)

        if human_count <= history_limit:
            logger.debug(
                f"TRIM - Nessun trimming necessario (humans={human_count} <= limit={history_limit})."
            )
            return messages

        # Primo HumanMessage da conservare
        start_human_idx = human_indices[-history_limit]
        start_idx = start_human_idx

        # Preserva un AIMessage immediatamente precedente (es. profilo utente)
        if start_idx > 0 and isinstance(messages[start_idx - 1], AIMessage):
            start_idx -= 1

        trimmed = messages[start_idx:]

        logger.info(
            "TRIM - Applicato trimming memoria: "
            f"tot={len(messages)} humans={human_count} limit={history_limit} "
            f"start_idx={start_idx} result_len={len(trimmed)}"
        )
        logger.debug(
            "TRIM - Tipi sequenza risultante: "
            + ",".join(type(m).__name__ for m in trimmed)
        )
        return trimmed
    except Exception as e:
        logger.error(f"TRIM - Errore durante il trimming dei messaggi: {e}")
        return messages

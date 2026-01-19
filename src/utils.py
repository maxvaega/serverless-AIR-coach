"""
Utility functions for user formatting, validation, document caching, and prompt management.
"""
from typing import Dict, Optional, Tuple
import datetime
import re
import logging
import threading

from .s3_utils import fetch_docs_from_s3

logger = logging.getLogger("uvicorn")


# ------------------------------------------------------------------------------
# User Metadata Formatting
# ------------------------------------------------------------------------------

JUMPS_MAPPING = {
    "0_10": "0 - 10",
    "11_50": "11 - 50",
    "51_150": "51 - 150",
    "151_300": "151 - 300",
    "301_1000": "301 - 1000",
    "1000+": "1000+",
}

QUALIFICATIONS_MAPPING = {
    "NO_PARACADUTISMO": "non ha mai fatto paracadutismo",
    "ALLIEVO": "allievo senza licenza",
    "LICENZIATO": "qualifica: Paracadutista licenziato",
    "DL": "qualifica: possiede la licenza di paracadutismo e la qualifica Direttore di lancio",
    "IP": "qualifica: possiede la qualifica da Istruttore di paracadutismo",
}

SEX_MAPPING = {
    "MASCHIO": "Maschio",
    "FEMMINA": "Femmina",
    "SCONOSCIUTO": "Preferisce non dirlo",
}


def _format_field(value: Optional[str], mapping: Dict[str, str], field_name: str) -> Optional[str]:
    """Format a field value using a mapping, logging warnings for unknown values."""
    if not value:
        return None
    formatted = mapping.get(value)
    if formatted is None:
        logger.warning(f"USER INFO - {field_name} non riconosciuto: {value}")
    return formatted


def format_user_metadata(user_metadata: Dict) -> str:
    """
    Formatta i metadata dell'utente in una stringa leggibile.
    """
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    if not user_metadata:
        logger.info("USER INFO - Nessun metadata utente trovato.")
        return f"\nOggi è il {date_str}\n"

    lines = ["I dati che l'utente ti ha fornito su di sè sono:"]

    # Date of Birth
    if dob := user_metadata.get("date_of_birth"):
        lines.append(f"Data di Nascita: {dob}")

    # Jumps
    if jumps := _format_field(user_metadata.get("jumps"), JUMPS_MAPPING, "Numero di salti"):
        lines.append(f"Numero di salti: {jumps}")

    # Preferred Dropzone
    if dropzone := user_metadata.get("preferred_dropzone"):
        lines.append(f"Dropzone preferita: {dropzone}")

    # Qualifications
    if qual := _format_field(user_metadata.get("qualifications"), QUALIFICATIONS_MAPPING, "Qualifica"):
        lines.append(qual)

    # Name and Surname
    name = user_metadata.get("name")
    surname = user_metadata.get("surname")
    if name:
        lines.append(f"Nome: {name}")
    if surname:
        lines.append(f"Cognome: {surname}")

    # Sex
    if sex := _format_field(user_metadata.get("sex"), SEX_MAPPING, "Sesso"):
        lines.append(f"Sesso: {sex}")

    lines.append(f"\nOggi è il {date_str}")

    logger.info(f"USER INFO - metadata salvati in cache per: {name} {surname}")

    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------
# User ID Validation
# ------------------------------------------------------------------------------

AUTH0_PATTERN = re.compile(r'^auth0\|[0-9a-fA-F]{24}$')
GOOGLE_PATTERN = re.compile(r'^google-oauth2\|[0-9]{15,25}$')


def validate_user_id(user_id: str) -> bool:
    """Validate user ID format for Auth0 or Google OAuth2."""
    return bool(AUTH0_PATTERN.match(user_id) or GOOGLE_PATTERN.match(user_id))


# ------------------------------------------------------------------------------
# Document Cache
# ------------------------------------------------------------------------------

class _DocsCache:
    """Thread-safe cache for S3 documents."""

    def __init__(self):
        self._lock = threading.Lock()
        self._content: Optional[str] = None
        self._meta: Optional[list] = None
        self._timestamp: Optional[datetime.datetime] = None

    def get(self) -> Optional[str]:
        """Get cached content, fetching from S3 if empty."""
        if self._content is None:
            self._fetch()
        return self._content

    def update(self) -> dict:
        """Force update from S3 and return result details."""
        with self._lock:
            return self._fetch()

    def _fetch(self) -> dict:
        """Fetch docs from S3 and update cache."""
        logger.info("Docs: Fetching from S3...")
        result = fetch_docs_from_s3()
        self._content = result["combined_docs"]
        self._meta = result["docs_meta"]
        self._timestamp = datetime.datetime.utcnow()
        logger.info("Docs: Cache updated successfully.")
        return {
            "message": "Document cache updated successfully.",
            "docs_count": len(self._meta),
            "docs_details": self._meta,
            "combined_docs": self._content,
        }


_docs_cache = _DocsCache()


def get_combined_docs() -> str:
    """Return combined docs content, using cache if available."""
    return _docs_cache.get() or ""


def update_docs_from_s3() -> dict:
    """Force refresh documents from S3."""
    return _docs_cache.update()


# ------------------------------------------------------------------------------
# Prompt Manager
# ------------------------------------------------------------------------------

class _PromptManager:
    """Thread-safe manager for system prompt with versioning."""

    def __init__(self):
        self._lock = threading.Lock()
        self._prompt: Optional[str] = None
        self._version: int = 0

    def get(self) -> str:
        """Get current system prompt."""
        return self._prompt or ""

    def get_with_version(self) -> Tuple[str, int]:
        """Get current prompt and version."""
        return (self.get(), self._version)

    def ensure_initialized(self) -> None:
        """Initialize prompt from docs cache if not already set."""
        if self._prompt:
            return
        with self._lock:
            if self._prompt:
                return
            docs = get_combined_docs()
            self._prompt = docs
            self._version = 1
            logger.info("PromptManager: system prompt inizializzato (v1).")

    def update_from_s3(self) -> dict:
        """Force update from S3 and increment version."""
        with self._lock:
            update = update_docs_from_s3()
            self._prompt = update.get("combined_docs", "")
            self._version = (self._version or 0) + 1
            logger.info(f"PromptManager: system prompt aggiornato (v{self._version}).")
            return {
                "message": update.get("message", "System prompt updated successfully."),
                "docs_count": update.get("docs_count", 0),
                "docs_details": update.get("docs_details", []),
                "system_prompt": self._prompt,
                "combined_docs": self._prompt,
                "prompt_version": self._version,
            }


_prompt_manager = _PromptManager()


# Public API for prompt management
def get_prompt() -> str:
    return _prompt_manager.get()


def get_prompt_with_version() -> Tuple[str, int]:
    return _prompt_manager.get_with_version()


def ensure_prompt_initialized() -> None:
    _prompt_manager.ensure_initialized()


def update_prompt_from_s3() -> dict:
    return _prompt_manager.update_from_s3()


# Legacy alias for backward compatibility
def build_system_prompt(docs: str) -> str:
    """Build system prompt from docs content. Kept for backward compatibility."""
    return docs

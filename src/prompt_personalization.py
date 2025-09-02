from typing import Optional, Tuple

from .auth0 import get_user_metadata
from .cache import get_cached_user_data, set_cached_user_data
from .logging_config import logger
from .utils import format_user_metadata, get_prompt_with_version


USER_SECTION_HEADER = "## Informazioni Utente Corrente"


def build_personalized_prompt(base_prompt: str, user_info: Optional[str]) -> str:
    """
    Concatena al prompt base una sezione con i dati utente (se presenti).
    """
    if not user_info:
        return base_prompt
    return f"""{base_prompt}

{USER_SECTION_HEADER}
{user_info}
Usa queste informazioni per adattare tono, contenuto ed esempi alle caratteristiche dell'utente.
"""


def get_personalized_prompt_for_user(
    user_id: str,
    token: Optional[str],
    fetch_user_data: bool = True,
) -> Tuple[str, int, Optional[str]]:
    """
    Ritorna (prompt_personalizzato, prompt_version, user_info_formattato).
    Il base prompt e la versione provengono dal PromptManager.
    """
    base_prompt, prompt_version = get_prompt_with_version()
    user_info = None

    if fetch_user_data:
        try:
            user_info = get_cached_user_data(user_id)
            if not user_info:
                logger.info(f"Auth0: fetch metadata for user {user_id}")
                metadata = get_user_metadata(user_id, token=token)
                user_info = format_user_metadata(metadata)
                if user_info:
                    set_cached_user_data(user_id, user_info)
        except Exception as e:
            logger.error(f"User metadata fetch error for {user_id}: {e}")
            user_info = None

    personalized_prompt = build_personalized_prompt(base_prompt, user_info)
    return personalized_prompt, prompt_version, user_info


def generate_thread_id(user_id: str, prompt_version: int) -> str:
    """
    Un solo thread per utente per versione di prompt.
    """
    return f"{user_id}:v{prompt_version}"



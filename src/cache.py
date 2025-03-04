# Gestisce la cache degli user data e del token Auth0
# TODO: inserire anche la cache dei docs

from cachetools import TTLCache
from typing import Optional

# Cache per i dati utente con TTL di 600 secondi (10 minuti)
user_metadata_cache = TTLCache(maxsize=1000, ttl=600)

# Cache per il token Auth0 con TTL di 86400 secondi (24 ore)
auth0_token_cache = TTLCache(maxsize=1, ttl=86400)

def get_cached_user_data(user_id: str) -> Optional[str]:
    """
    Recupera i dati utente dalla cache.
    
    :param user_id: L'ID dell'utente.
    :return: Stringa formattata con i dati utente o None se non presente.
    """
    return user_metadata_cache.get(user_id)

def set_cached_user_data(user_id: str, data: str):
    """
    Inserisce i dati utente nella cache.
    
    :param user_id: L'ID dell'utente.
    :param data: Stringa formattata con i dati utente.
    """
    user_metadata_cache[user_id] = data

def get_cached_auth0_token() -> Optional[str]:
    """
    Recupera il token Auth0 dalla cache.
    
    :return: Token Auth0 come stringa o None se non presente.
    """
    return auth0_token_cache.get('auth0_token')

def set_cached_auth0_token(token: str):
    """
    Inserisce il token Auth0 nella cache.
    
    :param token: Token Auth0 come stringa.
    """
    auth0_token_cache['auth0_token'] = token
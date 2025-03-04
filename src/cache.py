# Gestisce la cache degli user data
# TODO: inserire anche la cache dei docs

from cachetools import TTLCache
from typing import Dict

# Cache per i dati utente con TTL di 300 secondi (5 minuti)
user_metadata_cache = TTLCache(maxsize=1000, ttl=300)

def get_cached_user_data(user_id: str) -> str:
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

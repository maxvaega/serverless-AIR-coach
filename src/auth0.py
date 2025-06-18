import requests
from .env import AUTH0_DOMAIN
from .logging_config import logger
from typing import Optional

def get_user_metadata(user_id: str, token: Optional[str] = None) -> dict:
    """
    Recupera i metadata dell'utente da Auth0 utilizzando il token fornito o quello gestito tramite la cache.
    
    :param user_id: L'ID dell'utente.
    :param token: (opzionale) Token di accesso già verificato.
    :return: Dizionario contenente i metadata dell'utente.
    """
    if user_id == "string" or not user_id:
        logger.info(f"Auth0: user id fornito non valido: {user_id}")
        return {}
    if not token:
        logger.error("Auth0: Impossibile ottenere il token. Non è possibile recuperare i metadata utente.")
        return {}
    url = f"https://{AUTH0_DOMAIN}/api/v2/users/{user_id}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {token}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("user_metadata", {})
    except requests.exceptions.RequestException as e:
        logger.error(f"Auth0: Errore nella chiamata API di Auth0 per l'userid {user_id}: {e}")
        return {}
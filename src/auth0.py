import requests
from .env import AUTH0_DOMAIN, AUTH0_API_TOKEN
from .logging_config import logger

def get_user_metadata(user_id: str) -> dict:
    """
    Recupera i metadata dell'utente da Auth0.

    :param user_id: L'ID dell'utente.
    :return: Dizionario contenente i metadata dell'utente.
    """
    url = f"https://{AUTH0_DOMAIN}/api/v2/users/{user_id}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {AUTH0_API_TOKEN}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("user_metadata", {})
    except requests.exceptions.RequestException as e:
        logger.error(f"Errore nella chiamata API di Auth0: {e}")
        return {}
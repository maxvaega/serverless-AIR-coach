import requests
from app.config import settings
import logging
logger = logging.getLogger("uvicorn")
from .cache import set_cached_auth0_token, get_cached_auth0_token
from typing import Optional

def get_auth0_token() -> Optional[str]:
    """
    Ottiene un token di accesso da Auth0 utilizzando le credenziali client.
    
    :return: Token di accesso come stringa oppure None in caso di errore.
    """
    # Verifica se il token è già presente nella cache
    token = get_cached_auth0_token()
    if token:
        logger.info("Auth0: Token trovato in cache.")
        return token

    url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    headers = {
        'content-type': 'application/x-www-form-urlencoded'
    }
    payload = {
        'grant_type': 'client_credentials',
        'client_id': 'MRSjewKmL15bVGQoBWJlEFUTK57lykvj',
        'client_secret': settings.AUTH0_SECRET,
        'audience': f"https://{settings.AUTH0_DOMAIN}/api/v2/"
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        token_response = response.json()
        access_token = token_response.get('access_token')
        if access_token:
            # Salva il token nella cache con TTL di 86400 secondi (24 ore)
            set_cached_auth0_token(access_token)
            logger.info(f"Auth0: Token ottenuto e salvato in cache: {access_token}")
            return access_token
        else:
            logger.error("Auth0: Token non presente nella risposta.")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Auth0: Errore durante l'ottenimento del token: {e}")
        return None

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

    token = get_auth0_token()
    if not token:
        logger.error("Auth0: Impossibile ottenere il token Auth0. Non è possibile recuperare i metadata utente.")
        return {}
    url = f"https://{settings.AUTH0_DOMAIN}/api/v2/users/{user_id}"
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
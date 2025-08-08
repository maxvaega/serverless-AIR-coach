import pytest
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8080/api")

# Configurazione dell'URL API per i test - Scegliere l'URL API in base all'ambiente:
# Locale:       "http://localhost:8080/api" # Ricordarsi di lanciare il server locale
# Development:  "https://serverless-air-coach-git-develop-ai-struttore.vercel.app/api"
# Produzione:   "https://www.air-coach.it/api"


# Inserire qui un token JWT valido per i test e2e (può essere impostato via variabile d'ambiente)
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def is_token_configured():
    return AUTH_TOKEN and AUTH_TOKEN != ""

def get_test_auth_token() -> str:
    """
    Restituisce un token valido per i test:
    - Se `TEST_AUTH_TOKEN` è impostato, usa quello
    - Altrimenti prova a generarne uno tramite `src.auth0.get_auth0_token`
    Ritorna stringa vuota se non disponibile.
    """
    env_token = os.getenv("TEST_AUTH_TOKEN", "")
    if env_token:
        return env_token

    try:
        # Genera token usando la logica applicativa esistente
        from src.auth0 import get_auth0_token
        generated = get_auth0_token()
        print(f"Generated token: {generated}")
        return generated or ""
    except Exception as e:
        # Stampa diagnostica per capire eventuali problemi di import/ambiente
        import traceback
        print("get_test_auth_token exception:", repr(e))
        traceback.print_exc()
        return ""

def test_stream_query_invalid_token():
    """
    Test E2E: Verifica che /stream_query rifiuti richieste con token non valido.
    """
    payload = {
        "message": "Ciao, chi sei? [Test senza token valido]",
        "userid": "google-oauth2|104612087445133776110"
    }
    headers = HEADERS.copy()
    headers["Authorization"] = "Bearer invalidtoken"
    with httpx.Client(timeout=10) as client:
        response = client.post(f"{API_URL}/stream_query", json=payload, headers=headers)
        assert response.status_code in (401, 403)

def test_stream_query_no_token():
    """
    Test E2E: Verifica che /stream_query rifiuti richieste senza token (nessun header Authorization).
    Deve restituire 403.
    """
    payload = {
        "message": "Ciao, chi sei? [Test senza token]",
        "userid": "google-oauth2|104612087445133776110"
    }
    headers = {"Content-Type": "application/json"}  # Nessun Authorization
    with httpx.Client(timeout=10) as client:
        response = client.post(f"{API_URL}/stream_query", json=payload, headers=headers)
        assert response.status_code == 403

def test_stream_query_success():
    """
    Test E2E: Verifica che /stream_query risponda correttamente a una richiesta valida (streaming SSE).
    """
    payload = {
        "message": "Ciao chi sei? [Messaggio scritto per testare la risposta]",
        "userid": "google-oauth2|104612087445133776110"
    }
    token = get_test_auth_token()
    if not token:
        pytest.skip("Token di autenticazione non configurato e generazione automatica fallita")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    with httpx.Client(timeout=30) as client:
        with client.stream("POST", f"{API_URL}/stream_query", json=payload, headers=headers) as r:
            assert r.status_code == 200
            lines = list(r.iter_lines())
            assert any(line.strip().startswith("data:") for line in lines if line)

def test_stream_query_invalid_payload_422():
    # userid mancante → 422
    payload = {"message": "Messaggio senza userid"}
    token = get_test_auth_token()
    if not token:
        pytest.skip("Token di autenticazione non configurato e generazione automatica fallita")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=10) as client:
        r = client.post(f"{API_URL}/stream_query", json=payload, headers=headers)
        assert r.status_code == 422

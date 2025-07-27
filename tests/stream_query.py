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

@pytest.mark.skipif(not is_token_configured(), reason="Token di autenticazione non configurato. Esporta un token JWT valido nella variabile d’ambiente TEST_AUTH_TOKEN")
def test_stream_query_success():
    """
    Test E2E: Verifica che /stream_query risponda correttamente a una richiesta valida (streaming SSE).
    """
    payload = {
        "message": "Ciao chi sei? [Messaggio scritto per testare la risposta]",
        "userid": "google-oauth2|104612087445133776110"
    }
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{API_URL}/stream_query", json=payload, headers=headers)
        assert response.status_code == 200
        # Verifica che arrivi almeno un chunk che inizi con 'data:'
        chunks = list(response.iter_text())
        assert any(chunk.strip().startswith("data:") for chunk in chunks)

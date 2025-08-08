import pytest
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8080/api")

# Inserire qui un token JWT valido per i test e2e (può essere impostato via variabile d'ambiente)
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def is_token_configured():
    return AUTH_TOKEN and AUTH_TOKEN != ""

@pytest.mark.skipif(not is_token_configured(), reason="Token di autenticazione non configurato. Esporta un token JWT valido nella variabile d’ambiente TEST_AUTH_TOKEN")
def test_update_docs():
    """
    Test E2E: Verifica che l'endpoint /update_docs aggiorni la cache e restituisca i dettagli dei documenti.
    """
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{API_URL}/update_docs", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs_count" in data
        assert "docs_details" in data
        assert isinstance(data["docs_details"], list)
        assert "system_prompt" in data
        assert "prompt_file" in data

def test_update_docs_public():
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{API_URL}/update_docs")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs_count" in data
        assert "docs_details" in data and isinstance(data["docs_details"], list)
        assert "system_prompt" in data
        assert "prompt_file" in data

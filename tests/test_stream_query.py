import pytest
import httpx
import os
import json
from src.env import DATABASE_NAME, COLLECTION_NAME
from src.database import get_collection

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


def test_stream_query_saves_tool_result():
    """
    Test E2E: Verifica che una richiesta che triggera il tool salvi il campo 'tool' nel DB
    con nome tool e risultato prodotti dall'agente nell'ultima run in streaming.
    """
    user_id = "google-oauth2|104612087445133776110"
    payload = {
        "message": "fammi una domanda di teoria scelta casualmente. usa domanda_teoria",
        "userid": user_id,
    }

    token = get_test_auth_token()
    if not token:
        pytest.skip("Token di autenticazione non configurato e generazione automatica fallita")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    # Esegue la chiamata in streaming, verifica che nello stream compaia un `tool_result`
    # e poi consuma completamente lo stream per assicurare la persistenza su DB
    with httpx.Client(timeout=60) as client:
        with client.stream("POST", f"{API_URL}/stream_query", json=payload, headers=headers) as r:
            assert r.status_code == 200
            saw_tool_result = False
            saw_agent_message_after_tool = False
            for line in r.iter_lines():
                if not line:
                    continue
                if not str(line).startswith("data:"):
                    continue
                try:
                    payload_str = str(line)[len("data:"):].strip()
                    # Rimuovi eventuali escape sequences alla fine (sia literal che encoded)
                    if payload_str.endswith('\\n\\n'):
                        payload_str = payload_str[:-4]
                    elif payload_str.endswith('\n\n'):
                        payload_str = payload_str[:-2]
                    evt = json.loads(payload_str)
                except Exception:
                    continue
                if evt.get("type") == "tool_result":
                    saw_tool_result = True
                elif evt.get("type") == "agent_message" and saw_tool_result:
                    # Dopo un tool_result con return_direct non devono arrivare agent_message
                    saw_agent_message_after_tool = True
                # Consuma comunque tutto lo stream
            # Verifica che abbiamo ricevuto un evento tool_result
            assert saw_tool_result, "Nessun evento 'tool_result' ricevuto nello stream"
            # Con tool return-direct non dovrebbero arrivare agent_message successivi
            assert not saw_agent_message_after_tool, "Sono arrivati 'agent_message' dopo 'tool_result' (return-direct)"

    # Recupera l'ultimo documento per l'utente e verifica il campo 'tool'
    coll = get_collection(DATABASE_NAME, COLLECTION_NAME)
    last_doc_cursor = coll.find({"userId": user_id}).sort("timestamp", -1).limit(1)
    last_docs = list(last_doc_cursor)
    assert last_docs, "Nessun documento trovato per l'utente dopo la chiamata di streaming"
    doc = last_docs[0]

    assert "tool" in doc, "Campo 'tool' mancante nel documento salvato"
    tool_entry = doc["tool"]

    # Supporta sia singolo dict che lista di dict
    if isinstance(tool_entry, list):
        assert len(tool_entry) >= 1
        tool_item = tool_entry[0]
    else:
        tool_item = tool_entry

    assert isinstance(tool_item, dict)
    # Supporta sia schema vecchio (name/result) sia nuovo (tool_name/data)
    name = tool_item.get("name") or tool_item.get("tool_name")
    assert name == "domanda_teoria"
    result = tool_item.get("result") or tool_item.get("data")
    assert result is not None

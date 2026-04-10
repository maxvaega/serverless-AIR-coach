"""
Test E2E: Riproduce il bug 'Response' object is not subscriptable.

Scenario:
1. Chiede una domanda casuale di quiz
2. Risponde con la risposta corretta (letta dal tool_result)

Il bug si manifesta alla seconda richiesta, quando l'agente valuta la risposta
e tenta di chiamare domanda_teoria per la domanda successiva.

Richiede: server avviato con `python run.py`
"""
import pytest
import httpx
import json
import os
import time

pytestmark = pytest.mark.e2e

API_URL = os.getenv("API_URL", "http://localhost:8080/api")


def get_test_auth_token() -> str:
    env_token = os.getenv("TEST_AUTH_TOKEN", "")
    if env_token:
        return env_token
    try:
        from src.auth0 import get_auth0_token
        return get_auth0_token() or ""
    except Exception:
        return ""


def parse_sse_events(response) -> list[dict]:
    """Parsa tutti gli eventi SSE dallo stream e li ritorna come lista di dict."""
    events = []
    for line in response.iter_lines():
        if not line or not str(line).startswith("data:"):
            continue
        try:
            payload_str = str(line)[len("data:"):].strip()
            if payload_str.endswith('\\n\\n'):
                payload_str = payload_str[:-4]
            elif payload_str.endswith('\n\n'):
                payload_str = payload_str[:-2]
            evt = json.loads(payload_str)
            events.append(evt)
        except Exception:
            # Se c'e' un errore nel JSON, salvalo come raw
            events.append({"type": "parse_error", "raw": payload_str})
    return events


def extract_correct_answer(events: list[dict]) -> str | None:
    """Estrae la risposta corretta dal tool_result."""
    for evt in events:
        if evt.get("type") == "tool_result":
            data = evt.get("data", {})
            content = data.get("content", data)
            if isinstance(content, dict):
                return content.get("risposta_corretta")
    return None


def extract_text(events: list[dict]) -> str:
    """Concatena tutti i chunk di testo agent_message."""
    parts = []
    for evt in events:
        if evt.get("type") == "agent_message":
            parts.append(evt.get("data", ""))
    return "".join(parts)


def has_error(events: list[dict]) -> str | None:
    """Controlla se c'e' un evento di errore nello stream."""
    for evt in events:
        if "error" in evt:
            return evt["error"]
        if evt.get("type") == "parse_error":
            raw = evt.get("raw", "")
            if "error" in raw.lower():
                return raw
    return None


def send_message(client: httpx.Client, headers: dict, message: str, user_id: str) -> list[dict]:
    """Invia un messaggio al server e ritorna gli eventi SSE parsati."""
    payload = {"message": message, "userid": user_id}
    with client.stream("POST", f"{API_URL}/stream_query", json=payload, headers=headers) as r:
        assert r.status_code == 200, f"HTTP {r.status_code}"
        return parse_sse_events(r)


def test_multi_turn_quiz_no_error():
    """
    Riproduce il bug: due richieste sequenziali di quiz.
    1. 'Fammi una domanda di teoria' -> riceve domanda con risposta corretta
    2. Risponde con la lettera corretta -> deve funzionare senza errori
    """
    token = get_test_auth_token()
    if not token:
        pytest.skip("Token non configurato")

    user_id = "google-oauth2|104612087445133776110"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        # --- STEP 1: Chiedi una domanda casuale ---
        print("\n=== STEP 1: Richiesta domanda casuale ===")
        events1 = send_message(client, headers, "Fammi una domanda di teoria a caso", user_id)

        error1 = has_error(events1)
        assert error1 is None, f"Errore nella prima richiesta: {error1}"

        correct_answer = extract_correct_answer(events1)
        assert correct_answer is not None, (
            f"Risposta corretta non trovata nel tool_result.\n"
            f"Eventi ricevuti: {json.dumps(events1, indent=2, ensure_ascii=False)[:1000]}"
        )
        text1 = extract_text(events1)
        print(f"Testo LLM: {text1[:100]}...")
        print(f"Risposta corretta: {correct_answer}")

        # Piccola pausa per assicurarsi che il salvataggio DB sia completato
        time.sleep(1)

        # --- STEP 2: Rispondi con la risposta corretta ---
        print(f"\n=== STEP 2: Rispondo '{correct_answer}' ===")
        events2 = send_message(client, headers, correct_answer, user_id)

        error2 = has_error(events2)
        text2 = extract_text(events2)
        print(f"Testo LLM: {text2[:200]}...")

        # Verifica critica: nessun errore nella seconda risposta
        assert error2 is None, (
            f"BUG RIPRODOTTO! Errore nella seconda richiesta: {error2}\n"
            f"Eventi: {json.dumps(events2, indent=2, ensure_ascii=False)[:1000]}"
        )

        # Verifica che il testo contenga un riscontro positivo
        assert text2, "Nessun testo ricevuto nella seconda risposta"
        print("\nTest superato: nessun errore nel flusso multi-turn quiz")

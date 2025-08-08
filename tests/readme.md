# Test Plan per AIR Coach API

Questo documento descrive la suite di test end-to-end (E2E) pensata per essere eseguita con `pytest`. I test unitari sono al momento non sviluppati.

---

## 1. Test End-to-End (E2E)
stato: sviluppati

### 1.1. `/api/stream_query`
- Obiettivo: verificare che l'endpoint risponda correttamente a una richiesta autenticata, restituisca stream SSE valido e persista correttamente gli output dei tool.
- Test implementati:
  - Richiesta con token non valido → 401/403
  - Richiesta senza token → 403
  - Richiesta valida → 200 e presenza di linee SSE che iniziano con `data:`
  - Payload non valido → 422 (es. `userid` mancante) [richiede token valido]
  - Richiesta che triggera un tool → viene salvato in MongoDB il campo `tool` con `name` e `result`
- Dati:
  - `TEST_AUTH_TOKEN`: facoltativo. Se non impostato, i test che richiedono un token valido proveranno a generarlo automaticamente tramite `src.auth0.get_auth0_token()` (client credentials)
  - `userid`: parametrizzato (es. un `google-oauth2|...`)
  - `message`: parametrizzato
- Note SSE:
  - I test consumano lo stream in modalità line-based per verificare correttamente i chunk SSE (`iter_lines`).

### 1.2. `/api/update_docs`
- Obiettivo: verificare che l’aggiornamento dei documenti aggiorni la cache e il system prompt.
- Test implementati:
  - Richiesta valida → 200 e presenza di `message`, `docs_count`, `docs_details` (lista), `system_prompt`, `prompt_file`
- Autenticazione:
  - Endpoint pubblico: non richiede `TEST_AUTH_TOKEN`

---

## 2. Unit Test
stato: non sviluppati

### 2.1. `src/rag.py`
- ask: stream/non-stream, `user_data=True`, `chat_history=True`
- update_docs: aggiornamento cache e dettagli

### 2.2. `src/auth.py`
- VerifyToken: JWT valido/non valido

### 2.3. `src/auth0.py`
- get_auth0_token: recupero/caching
- get_user_metadata: mock API

### 2.4. `src/cache.py`
- cache metadati/token

### 2.5. `src/database.py`
- insert/find/drop (mock MongoDB)

### 2.6. `src/utils.py`
- format_user_metadata
- validate_user_id

---

## 3. Mock e Setup
tbd

---

## 4. Ambito dei test
- Disponibile:
  - E2E `/api/stream_query`: invalid token, no token, successo (SSE), payload non valido (422)
  - E2E `/api/update_docs`: successo
- Non disponibile:
  - E2E errori S3 per `/api/update_docs` (500)
  - Tutti i test unitari (backlog)

---

## 5. Comando di esecuzione

```sh
pytest -v -rs tests/
```

---

## 6. Istruzioni

1) Installa le dipendenze:
```sh
pip install pytest httpx
```

2) (Opzionale) Esporta un token JWT valido per i test che richiedono autenticazione:
```sh
export TEST_AUTH_TOKEN="il_tuo_token_jwt_valido"
```
   - Se non imposti `TEST_AUTH_TOKEN`, i test proveranno a ottenere un token tramite `src.auth0.get_auth0_token()` usando le variabili di ambiente Auth0 (`AUTH0_DOMAIN`, `AUTH0_SECRET`, `AUTH0_API_AUDIENCE`, `AUTH0_ISSUER`). In caso di fallimento, i test interessati verranno marcati come `skipped`.

3) (Facoltativo) Seleziona l'URL del server da testare (default: `http://localhost:8080/api`)
```sh
export API_URL="https://server-da-testare/api"
```

4) Avvia il backend e lancia i test:
```sh
# Tutti i test
pytest -v -rs tests/

# Solo stream_query
pytest -v -rs tests/stream_query.py

# Solo update_docs (non richiede TEST_AUTH_TOKEN)
pytest -v -rs tests/update_docs.py
```

---

## 7. Note operative
- I test E2E dipendono da servizi esterni reali (Auth0, S3, MongoDB) e possono fallire in assenza di configurazioni o disponibilità dei servizi.
- `API_URL` può puntare a ambienti diversi (locale, dev, prod).
 - La generazione automatica del token usa un token di tipo client credentials; deve essere compatibile con la verifica JWT dell'API (audience/issuer coerenti). In caso contrario, imposta manualmente `TEST_AUTH_TOKEN`.
 - `tests/conftest.py` aggiunge la root del progetto al `PYTHONPATH` per consentire gli import da `src.*` durante l'esecuzione di pytest.

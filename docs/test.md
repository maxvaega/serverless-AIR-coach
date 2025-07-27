# Test Plan per AIR Coach API

Questo documento descrive una suite di test end-to-end (E2E) e unitari per validare il funzionamento della codebase AIR Coach API. Tutti i test sono pensati per essere eseguiti con `pytest`.

---

## 1. Test End-to-End (E2E)
stato: sviluppati

### 1.1. `/api/stream_query`
- **Obiettivo:** Verificare che l'endpoint risponda correttamente a una richiesta autenticata e restituisca uno stream valido.
- **Test:**
  - Invio di una richiesta POST con JWT valido e payload conforme a `MessageRequest`.
  - Verifica che la risposta sia uno stream SSE e contenga una risposta coerente. Nessuna logica per verificare il contenuto della risposta, solo il formato.
  - Verifica che la chat venga salvata su MongoDB (saltare questo passo per adesso)
  - Test con JWT non valido → risposta 401/403.
  - Test con payload non valido → risposta 422.
- **Dati:**
  - token valido: fornito dall'utente a runtime (il token scade).
  - userid: parametrizzato nell'applicazione
  - message: parametrizzato nell'applicazione

### 1.2. `/api/update_docs`
- **Obiettivo:** Verificare che l'aggiornamento dei documenti aggiorni la cache e il system prompt.
- **Test:**
  - Invio di una richiesta POST.
  - Verifica che la risposta contenga i dettagli aggiornati dei documenti e il nuovo prompt.
  - Simulazione di errore S3 → risposta 500 (saltare questo passo per adesso).

---

## 2. Unit Test
stato: da sviluppare

### 2.1. `src/rag.py`
- **ask**
  - Test con parametri minimi → risposta non vuota.
  - Test con `user_data=True` → verifica che i metadati utente siano inclusi.
  - Test con `chat_history=True` → verifica che la storia venga recuperata.
  - Test con `stream=True` → verifica che venga restituito un generatore.
- **update_docs**
  - Test che aggiorni la cache e restituisca i dettagli corretti.

### 2.2. `src/auth.py`
- **VerifyToken**
  - Test con JWT valido → payload corretto.
  - Test con JWT non valido → eccezione.

### 2.3. `src/auth0.py`
- **get_auth0_token**
  - Test recupero token e caching.
- **get_user_metadata**
  - Test recupero metadati utente (mock API).

### 2.4. `src/cache.py`
- Test inserimento e recupero dati utente.
- Test inserimento e recupero token.

### 2.5. `src/database.py`
- Test inserimento, recupero e cancellazione dati (mock MongoDB).

### 2.6. `src/utils.py`
- Test formattazione metadati utente.
- Test validazione user_id.

---

## 3. Mock e Setup
- Utilizzare `pytest` e `pytest-mock` per mockare:
  - Chiamate esterne (Auth0, S3, MongoDB).
  - Variabili d'ambiente.
- Utilizzare `testclient` di FastAPI per E2E.

---

## 4. Esempio di struttura test

```
tests/
  test_app_e2e.py
  test_rag.py
  test_auth.py
  test_auth0.py
  test_cache.py
  test_database.py
  test_utils.py
```

---

## 5. Comando di esecuzione

```sh
pytest  -v -rs tests/
```

---

## 6. Istruzioni

Per eseguire i test:

1. Installa le dipendenze:

    ```sh
    pip install pytest httpx
    ```

2. Esporta un token JWT valido nella variabile d’ambiente TEST_AUTH_TOKEN:

    ```sh
    export TEST_AUTH_TOKEN="il_tuo_token_jwt_valido"
    ```

3. (facoltativo) Seleziona l'url del server che vuoi testare - in caso contrario si connetterà automaticamente a localhost:8080/api

    ```sh
    export API_URL="http://www.testserver.com/api"
    ```

4. Avvia il backend e lancia:

    ```sh
    pytest -v -rs tests/stream_query.py
    ```

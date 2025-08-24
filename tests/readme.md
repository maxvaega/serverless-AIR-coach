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
  - Richiesta che triggera un tool →
    - nello stream deve comparire un evento `tool_result` e, se il tool è `return_direct`, non devono comparire `agent_message` successivi
    - viene salvato in MongoDB il campo `tool` con `name` e `result`
- Dati:
  - `TEST_AUTH_TOKEN`: facoltativo. Se non impostato, i test che richiedono un token valido proveranno a generarlo automaticamente tramite `src.auth0.get_auth0_token()` (client credentials)
  - `userid`: parametrizzato (es. un `google-oauth2|...`)
  - `message`: parametrizzato
- Note SSE:
  - I test consumano lo stream in modalità line-based per verificare correttamente i chunk SSE (`iter_lines`).
  - Con tool marcati `return_direct` ci si aspetta che lo stream termini subito dopo l'evento `tool_result` senza ulteriori `agent_message`.

### 1.2. `/api/update_docs`
- Obiettivo: verificare che l’aggiornamento dei documenti aggiorni la cache e il system prompt.
- Test implementati:
  - Richiesta valida → 200 e presenza di `message`, `docs_count`, `docs_details` (lista), `system_prompt`, `prompt_file`
- Autenticazione:
  - Endpoint pubblico: non richiede `TEST_AUTH_TOKEN`

---

## 2. Unit Test
stato: parzialmente sviluppati

### 2.1. `src/tools.py` - Tool domanda_teoria
- **Stato**: ✅ Sviluppati
- **Obiettivo**: Testare tutte le funzionalità del tool domanda_teoria
- **Test implementati**:
  - **Domande casuali**: Recupero di domande casuali da tutto il database
  - **Domande per capitolo**: Recupero di domande casuali da capitoli specifici (1-10)
  - **Domande specifiche**: Ricerca di domande per numero e capitolo esatti
  - **Ricerca testuale**: Ricerca fuzzy case-insensitive nel testo delle domande
  - **Validazione input**: Controllo dei parametri (capitoli validi, testo minimo 3 caratteri)
  - **Gestione errori**: Gestione robusta di database vuoto, capitoli non validi, domande non trovate
  - **Formato output**: Verifica della consistenza e struttura dell'output
  - **Priorità parametri**: Verifica della logica di priorità tra i parametri di input
- **File**: `tests/test_tools.py`
- **Esecuzione**: `pytest -v -rs tests/test_tools.py`
- **Copertura**: 11 test che coprono tutti i casi d'uso e scenari di errore

### **Casi d'uso del Tool domanda_teoria**

Il tool `domanda_teoria` supporta i seguenti scenari di utilizzo, tutti testati nella suite:

#### **1. Domande Casuali**
- **Nessun parametro**: Restituisce una domanda casuale da tutto il database
- **Parametro `capitolo`**: Restituisce una domanda casuale dal capitolo specificato (1-10)

#### **2. Domande Specifiche**
- **Parametri `capitolo` + `domanda`**: Restituisce la domanda esatta per numero e capitolo

#### **3. Ricerca Testuale**
- **Parametro `testo`**: Ricerca fuzzy case-insensitive nel testo delle domande
- **Validazione**: Testo minimo di 3 caratteri richiesto

#### **4. Logica di Priorità**
1. **`testo`** (ricerca testuale) - Priorità massima
2. **`capitolo` + `domanda`** (domanda specifica)
3. **`capitolo`** (domanda casuale dal capitolo)
4. **Nessun parametro** (domanda casuale globale)

#### **5. Validazione e Gestione Errori**
- **Capitoli validi**: Solo valori da 1 a 10
- **Testo minimo**: Almeno 3 caratteri per la ricerca
- **Database vuoto**: Gestione appropriata quando non ci sono domande
- **Risultati non trovati**: Messaggi di errore informativi per ogni scenario

#### **6. Formato Output**
- **Struttura consistente**: Tutti i campi richiesti sempre presenti
- **Opzioni standardizzate**: Formato uniforme per le opzioni di risposta
- **Compatibilità JSON**: Output sempre serializzabile

### 2.2. `src/rag.py`
- ask: stream/non-stream, `user_data=True`, `chat_history=True`
- update_docs: aggiornamento cache e dettagli

### 2.3. `src/auth.py`
- VerifyToken: JWT valido/non valido

### 2.4. `src/auth0.py`
- get_auth0_token: recupero/caching
- get_user_metadata: mock API

### 2.5. `src/cache.py`
- cache metadati/token

### 2.6. `src/database.py`
- insert/find/drop (mock MongoDB)

### 2.7. `src/utils.py`
- format_user_metadata
- validate_user_id

---

## 3. Mock e Setup
- **Tool domanda_teoria**: ✅ Mock completo del servizio database con fixture pytest
- **Altri moduli**: tbd

---

## 4. Ambito dei test
- Disponibile:
  - E2E `/api/stream_query`: invalid token, no token, successo (SSE), payload non valido (422)
  - E2E `/api/update_docs`: successo
  - **Unit test `src/tools.py`**: ✅ Completamente sviluppati
- Non disponibile:
  - E2E errori S3 per `/api/update_docs` (500)
  - Altri test unitari (backlog)

---

## 5. Comando di esecuzione

```sh
# Tutti i test
pytest -v -rs tests/

# Solo test E2E
pytest -v -rs tests/stream_query.py
pytest -v -rs tests/update_docs.py

# Solo test unitari del tool
pytest -v -rs tests/test_tools.py

# Test specifici del tool
pytest -v -rs tests/test_tools.py::TestDomandaTeoria::test_domanda_casuale_success
pytest -v -rs tests/test_tools.py::TestDomandaTeoria::test_ricerca_per_testo_success

# Test per funzionalità specifiche
pytest -v -rs tests/test_tools.py -k "casuale"           # Solo test per domande casuali
pytest -v -rs tests/test_tools.py -k "capitolo"          # Solo test per capitoli
pytest -v -rs tests/test_tools.py -k "testo"             # Solo test per ricerca testuale
pytest -v -rs tests/test_tools.py -k "validazione"       # Solo test di validazione
pytest -v -rs tests/test_tools.py -k "errore"            # Solo test di gestione errori
```

---

## 6. Istruzioni

1) Installa le dipendenze:
```sh
pip install pytest httpx
```

2) (Opzionale) Esporta un token JWT valido per i test che richiedono autenticazione. passaggio opzionale perchè lo script può generare il proprio token prima di simulare le chiamate:
```sh
export TEST_AUTH_TOKEN="il_tuo_token_jwt_valido"
```
   - Se non imposti `TEST_AUTH_TOKEN`, i test proveranno a ottenere un token tramite `src.auth0.get_auth0_token()` usando le variabili d'ambiente Auth0 (`AUTH0_DOMAIN`, `AUTH0_SECRET`, `AUTH0_API_AUDIENCE`, `AUTH0_ISSUER`). In caso di fallimento, i test interessati verranno marcati come `skipped`.

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

# Solo test del tool domanda_teoria
pytest -v -rs tests/test_tools.py
```

**Nota sui test del tool**: I test unitari del tool `domanda_teoria` sono completamente isolati e non richiedono:
- Connessione al database MongoDB
- Configurazione di servizi esterni
- Token di autenticazione
- Avvio del server backend

Possono essere eseguiti immediatamente dopo l'installazione delle dipendenze pytest.

---

## 7. Note operative
- I test E2E dipendono da servizi esterni reali (Auth0, S3, MongoDB) e possono fallire in assenza di configurazioni o disponibilità dei servizi.
- **I test unitari del tool domanda_teoria sono completamente isolati** e usano mock per non dipendere da servizi esterni.
- **Copertura test unitari**: 11 test che coprono tutti i casi d'uso del tool domanda_teoria
- **Isolamento**: I test unitari utilizzano `unittest.mock.Mock` e `patch` per isolare completamente il tool dalle dipendenze esterne
- `API_URL` può puntare a ambienti diversi (locale, dev, prod).
- La generazione automatica del token usa un token di tipo client credentials; deve essere compatibile con la verifica JWT dell'API (audience/issuer coerenti). In caso contrario, imposta manualmente `TEST_AUTH_TOKEN`.
- `tests/conftest.py` aggiunge la root del progetto al `PYTHONPATH` per consentire gli import da `src.*` durante l'esecuzione di pytest.

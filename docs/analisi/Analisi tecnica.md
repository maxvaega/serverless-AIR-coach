# Analisi Tecnica dell'Architettura AIR Coach API

## Panoramica dell'Architettura

L'applicazione AIR Coach API è una piattaforma backend per chatbot, sviluppata in FastAPI, che integra autenticazione Auth0, gestione della cache, recupero dinamico di system prompt da file Markdown su AWS S3, interazione con LLM (Gemini 2.0 Flash) e persistenza su MongoDB. L'architettura è modulare e separa chiaramente le responsabilità tra i componenti.

## Flusso End-to-End: /stream_query

1. **Autenticazione**: L'endpoint `/api/stream_query` richiede autenticazione JWT tramite Auth0, validata dalla classe `VerifyToken` (src/auth.py).
2. **Ricezione Richiesta**: Il payload deve essere conforme al modello `MessageRequest` (src/models.py).
3. **Costruzione Prompt**: Il system prompt viene costruito combinando i file Markdown dal bucket S3 (src/rag.py), con eventuali metadati utente recuperati da Auth0 e formattati.
4. **Gestione Chat History**: Se richiesto, vengono recuperati gli ultimi 10 messaggi dalla collezione MongoDB e aggiunti al contesto.
5. **Chiamata LLM**: Il prompt viene inviato al modello Gemini 2.0 Flash tramite langchain_google_genai. Se `stream=True`, la risposta viene inviata come stream SSE.
6. **Persistenza**: Al termine dello streaming, domanda e risposta vengono salvate su MongoDB.

## Relazioni tra i File

```
app.py
├── src/models.py (MessageRequest, MessageResponse)
├── src/logging_config.py (logger)
├── src/rag.py (ask, update_docs, create_prompt_file)
├── src/env.py (variabili d'ambiente)
├── src/auth.py (VerifyToken)
└── src/auth0.py (get_user_metadata)
    ├── src/cache.py (cache user/token)
    └── src/utils.py (format_user_metadata)
├── src/database.py (get_data, insert_data, ensure_indexes)
└── src/logging_config.py (logger)
```

- **app.py**: Interfaccia principale tra client e logica di business, definisce gli endpoint FastAPI e la configurazione CORS.
- **src/rag.py**: Gestione system prompt, interazione con LLM, recupero/salvataggio chat, aggiornamento documenti S3.
- **src/auth.py**: Verifica e decodifica JWT Auth0.
- **src/auth0.py**: Recupero metadati utente da Auth0, gestione token con cache.
- **src/cache.py**: Cache in-memory per metadati utente e token Auth0.
- **src/database.py**: CRUD su MongoDB.
- **src/env.py**: Gestione variabili d'ambiente e configurazione.
- **src/utils.py**: Utility per formattazione metadati e validazione user_id.
- **src/models.py**: Modelli Pydantic per request/response.
- **src/logging_config.py**: Configurazione logging.
- **src/test.py**: Script CLI per testare la funzione ask.

## Interfacce tra le Funzioni Principali

### API (app.py) → Logica RAG (src/rag.py)

- **ask(query, user_id, chat_history, stream, user_data)**
  - Parametri: query (str), user_id (str), chat_history (bool), stream (bool), user_data (bool)
  - Ritorno: se stream=False, oggetto AIMessage; se stream=True, generatore asincrono per streaming SSE.
  - Stato condiviso: system_prompt, variabili d'ambiente (DATABASE_NAME, COLLECTION_NAME)

- **update_docs()**
  - Parametri: nessuno
  - Ritorno: dict con message, docs_count, docs_details, system_prompt
  - Stato condiviso: _docs_cache, combined_docs, system_prompt

### Gestione Documenti S3 (src/rag.py)
- Scarica e combina file Markdown da S3, aggiorna cache e system prompt.
- Permette aggiornamento manuale tramite endpoint `/api/update_docs`.

### Gestione Utente e Cache
- Recupero metadati utente da Auth0 (`get_user_metadata`), formattazione (`format_user_metadata`), caching (`set_cached_user_data`, `get_cached_user_data`).
- Token Auth0 gestito e cacheato per ridurre chiamate ripetute.

### Persistenza Chat
- Salvataggio e recupero conversazioni su MongoDB (`insert_data`, `get_data`).

## Analisi dei Moduli/File

### app.py
- Definisce l'app FastAPI, registra router, configura CORS.
- Endpoint principali:
  - `/api/stream_query`: POST, protetto, gestisce chat in streaming.
  - `/api/update_docs`: POST, aggiorna cache documenti e system prompt da S3.
- Autenticazione tramite `VerifyToken`.

### src/rag.py
- Gestione system prompt e documenti S3 (fetch, cache, update).
- Funzione principale `ask`: costruisce contesto, invoca LLM, gestisce streaming e persistenza.
- `create_prompt_file`: salva system prompt su S3.

### src/auth.py
- Classe `VerifyToken`: verifica JWT Auth0 tramite PyJWT e JWKS.
- Gestione eccezioni per autenticazione/autorizzazione.

### src/auth0.py
- `get_auth0_token`: ottiene e cachea token Auth0.
- `get_user_metadata`: recupera metadati utente da Auth0.

### src/cache.py
- Cache in-memory per metadati utente (TTL 10 min) e token Auth0 (TTL 24h).

### src/database.py
- Connessione a MongoDB, funzioni CRUD, gestione indici.

### src/env.py
- Caricamento variabili d'ambiente, configurazione Auth0, MongoDB, AWS, Google.

### src/utils.py
- `format_user_metadata`: formatta metadati utente.
- `validate_user_id`: regex per validazione user_id Auth0/Google.

### src/models.py
- Modelli Pydantic: `MessageRequest`, `MessageResponse`.

### src/logging_config.py
- Logger globale su stdout, livello INFO.

### src/test.py
- Script CLI per testare la funzione `ask` da terminale.

## Considerazioni Finali

- **Sicurezza**: Endpoint protetti da JWT Auth0.
- **Scalabilità**: Uso di cache locale per ridurre chiamate a servizi esterni.
- **Estendibilità**: Modularità elevata, facile aggiungere endpoint o provider LLM.
- **Persistenza**: Tutte le interazioni vengono salvate su MongoDB.
- **Prompt Dinamico**: Il system prompt può essere aggiornato senza riavviare il servizio, aggiornando i file su S3 e chiamando `/api/update_docs`.

## Riferimenti ai file principali

- app.py
- src/rag.py
- src/auth.py
- src/auth0.py
- src/cache.py
- src/database.py
- src/env.py
- src/utils.py
- src/models.py
- src/logging_config.py
- src/test.py

---

Per approfondimenti su una funzione specifica, consultare i file e le funzioni sopra elencate.
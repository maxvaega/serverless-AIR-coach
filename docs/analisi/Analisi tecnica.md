# Analisi Tecnica dell'Architettura AIR Coach API

## Panoramica dell'Architettura

L'applicazione AIR Coach API è una piattaforma backend per chatbot, sviluppata in FastAPI e **deployata su Vercel Serverless**, che integra autenticazione Auth0, gestione della cache, recupero dinamico di system prompt da file Markdown su AWS S3, interazione con LLM (Gemini 2.5 Flash), gestione tool con streaming e persistenza su MongoDB. L'architettura è modulare e separa chiaramente le responsabilità tra i componenti, ottimizzata per l'ambiente serverless e **integrata con LangGraph per la gestione di agenti AI avanzati**.

## Flusso End-to-End: /stream_query

1. **Autenticazione**: L'endpoint `/api/stream_query` richiede autenticazione JWT tramite Auth0, validata dalla classe `VerifyToken` (src/auth.py).
2. **Ricezione Richiesta**: Il payload deve essere conforme al modello `MessageRequest` (src/models.py).
3. **Agente LangGraph**: l'agente è costruito per-request con `create_react_agent(model, tools, prompt=personalized_prompt, pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT), checkpointer=InMemorySaver())`. Il `personalized_prompt` deriva dal PromptManager (base prompt versionato) con sezione dati utente concatenata al system prompt. Il checkpointer è condiviso a livello di processo per mantenere la memoria volatile dei thread tra richieste finché il container resta caldo.
4. **Gestione Memoria Ibrida e Versioning Thread**:
   - Si prepara `config={"configurable": {"thread_id": userid}}`.
   - Con il versioning del prompt, il thread è versionato: `thread_id = f"{userid}:v{prompt_version}"`. In questo modo la memoria volatile è isolata tra versioni del system prompt e non viene riutilizzata accidentalmente dopo un update.
   - Si legge lo stato del thread: se la memoria volatile contiene `messages`, la si usa direttamente.
   - Se è vuota, si preleva la storia da MongoDB (ultimi N turni), si ricostruiscono `HumanMessage`/`AIMessage`/`ToolMessage` e, se presenti, i risultati tool storici come contesto, poi si effettua `update_state(config, {"messages": seed_messages})`.
   - Coerenza warm/cold: in cold start la storia letta da DB può essere limitata; in warm path non viene applicato alcun trimming della memoria volatile. La finestra effettiva passata all'LLM è limitata agli ultimi `HISTORY_LIMIT` turni tramite `pre_model_hook` che imposta `llm_input_messages`, senza modificare lo stato `messages` del grafo.
5. **Invocazione in streaming**: si invia solo il messaggio corrente (`{"messages": [HumanMessage(query)]}`), affidando lo storico al checkpointer; il `pre_model_hook` limita la finestra lato input modello.
6. **Gestione Eventi Tool e AI**:
   - Eventi `on_tool_end`: catturano risultati tool, li serializzano con `_serialize_tool_output()` e li streamano come `tool_result`.
   - Se il tool è marcato come "return-direct" (vedi `src/tools.py`), l'agente termina l'esecuzione dopo `on_tool_end` e non vengono emessi `agent_message` successivi.
   - Eventi `on_chat_model_stream`: streamano chunk di risposta AI come `agent_message` solo quando non è stato eseguito un tool return-direct.
7. **Persistenza**: su MongoDB si salva la tripletta `human`/`system`/`tool` (se presente), insieme a `userId` e `timestamp`. In caso di tool return-direct, il campo `system` può essere vuoto e il risultato è rappresentato nel campo `tool`.

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
├── src/tools.py (domanda_teoria)
├── src/services/database/ (QuizMongoDBService, MongoDBService)
└── src/logging_config.py (logger)
```

- **app.py**: Interfaccia principale tra client e logica di business, definisce gli endpoint FastAPI e la configurazione CORS.
- **src/rag.py**: Gestione system prompt, interazione con LLM, recupero/salvataggio chat, aggiornamento documenti S3, serializzazione tool output.
- **src/auth.py**: Verifica e decodifica JWT Auth0.
- **src/auth0.py**: Recupero metadati utente da Auth0, gestione token con cache.
- **src/cache.py**: Cache in-memory per metadati utente e token Auth0.
- **src/database.py**: CRUD su MongoDB.
- **src/env.py**: Gestione variabili d'ambiente e configurazione.
- **src/utils.py**: Utility per formattazione metadati e validazione user_id.
- **src/models.py**: Modelli Pydantic per request/response.
- **src/tools.py**: **Implementazione dei tool utilizzabili dall'agente, incluso il tool domanda_teoria per la gestione dei quiz.**
- **src/services/database/**: **Servizi specializzati per l'interazione con MongoDB, inclusi QuizMongoDBService per la gestione dei quiz.**
- **src/logging_config.py**: Configurazione logging.
- **src/test.py**: Script CLI per testare la funzione ask.
- **tests/**: **Suite completa di test unitari e end-to-end per garantire la qualità del codice.**

## Autenticazione

- `/api/stream_query`: richiede Bearer JWT valido emesso da Auth0. La verifica usa JWKS (`src/auth.py`), controllando `audience` e `issuer` configurati.
- `/api/update_docs`: endpoint pubblico (nessuna autenticazione richiesta).

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

### Gestione Tool e Serializzazione

- **_serialize_tool_output(tool_output)**
  - Parametri: tool_output (qualsiasi tipo)
  - Ritorno: dict JSON-compatibile
  - Gestisce: ToolMessage, dict, list, str, int, float, bool e conversione generica

- **Gestione Eventi Tool**:
  - `on_tool_end`: cattura risultati, serializza e streams come `tool_result`
  - Salvataggio: tool_records in MongoDB con struttura `{"name": str, "result": dict}`

### **Gestione Quiz e Tool domanda_teoria**

- **QuizMongoDBService**: Servizio specializzato per la gestione dei quiz con metodi:
  - `get_random_question()`: Domanda casuale da tutto il database
  - `get_random_question_by_field(field, value)`: Domanda casuale da un campo specifico
  - `get_question_by_capitolo_and_number(capitolo, numero)`: Domanda specifica per capitolo e numero
  - `search_questions_by_text(testo)`: Ricerca fuzzy case-insensitive nel testo delle domande

- **Tool domanda_teoria**: Tool LangGraph che implementa:
  - Validazione input (capitoli 1-10, testo minimo 3 caratteri)
  - Logica di priorità parametri
  - Gestione errori robusta
  - Formato output consistente e strutturato

### Gestione Documenti S3 (src/rag.py)
- Scarica e combina file Markdown da S3, aggiorna cache e system prompt.
- Permette aggiornamento manuale tramite endpoint `/api/update_docs`.

### PromptManager e Versioning del System Prompt
- Il system prompt è gestito da un PromptManager process‑global in `src/utils.py` che mantiene:
  - `current_system_prompt`: prompt corrente in memoria di processo
  - `prompt_version`: intero incrementale che rappresenta la versione del prompt
  - locking thread‑safe per aggiornamenti atomici
- All'avvio/cold start, `ensure_prompt_initialized()` costruisce il prompt dai documenti in cache (`get_combined_docs()`), senza creare oggetti legati all'event loop.
- Ad ogni chiamata di `ask()` viene letto `(prompt, version)` tramite `get_prompt_with_version()`, personalizzato con i dati utente e usato per costruire l'agente per‑request.
- Il `thread_id` usato dal checkpointer è versionato (`{userid}:v{version}`) per isolare la memoria tra versioni diverse del prompt (1 thread per utente per versione).

### Aggiornamento Documenti e Prompt (`/api/update_docs`)
- L'endpoint invoca `update_prompt_from_s3()` che:
  - forza l'aggiornamento della cache dei documenti da S3 (contenuto combinato + metadati)
  - ricostruisce il vero system prompt con `build_system_prompt(combined_docs)`
  - effettua lo swap atomico del prompt corrente nel PromptManager e incrementa `prompt_version`
- La risposta dell'endpoint include:
  - `message`: esito dell'aggiornamento
  - `docs_count`: numero di documenti
  - `docs_details`: metadati dei documenti
  - `system_prompt`: prompt finale costruito
  - `combined_docs`: contenuto combinato (per trasparenza/debug)
  - `prompt_version`: versione corrente del prompt dopo l'update

Nota: la memoria volatile pre‑esistente per `thread_id` non viene cancellata ma diventa “isolata” perché le nuove esecuzioni usano un `thread_id` con versione aggiornata. Questo evita cross‑contamination fra prompt diversi e mantiene la compatibilità serverless.

### Gestione Utente e Cache
- Recupero metadati utente da Auth0 (`get_user_metadata`), formattazione (`format_user_metadata`), caching (`set_cached_user_data`, `get_cached_user_data`).
- Token Auth0 gestito e cacheato per ridurre chiamate ripetute.

### Persistenza Chat e Normalizzazione DB
- **Short-term**: `InMemorySaver` (volatile) condiviso a livello di processo con `thread_id` per persistere lo stato tra richieste nello stesso container caldo. Non si applica trimming in warm path; il limite per l'LLM viene applicato a runtime via `pre_model_hook`.
- **Long-term**: MongoDB, con lettura/ricostruzione storia alla cold start o quando la memoria volatile del thread è assente.
- **Normalizzazione DB**: `MongoDBService` converte tutti gli output letti dal DB in strutture JSON-serializzabili (es. `ObjectId` → `str`, `tuple/set` → `list`) a livello di servizio, così i consumer ricevono sempre oggetti JSON-safe.
- **Schema documento**: `human` (domanda), `system` (risposta), `tool` (opzionale: dict con `tool_name` e `data` serializzato), `userId`, `timestamp`.

## Analisi dei Moduli/File

### app.py
- Definisce l'app FastAPI, registra router, configura CORS.
- Endpoint principali:
  - `/api/stream_query`: POST, protetto, gestisce chat in streaming con tool.
  - `/api/update_docs`: POST, aggiorna cache documenti e system prompt da S3.
- Autenticazione tramite `VerifyToken`.

### src/rag.py
- **Gestione system prompt e documenti S3** (fetch, cache, update).
- **Agente LangGraph** creato per-request con `prompt` e `InMemorySaver` per evitare problemi di event loop chiuso su serverless.
- **Funzione `ask`**: memoria ibrida (checkpointer volatile per thread + seed da MongoDB alla cold start), streaming SSE con gestione separata tool/AI, estrazione e serializzazione `ToolMessage`, persistenza tripletta `human/system/tool`. System prompt personalizzato con dati utente concatenati; nessun `AIMessage` dedicato ai dati utente.
- **`_serialize_tool_output`**: serializza output tool per compatibilità JSON.
- **`create_prompt_file`**: salva system prompt su S3.

### src/tools.py
- **Implementa i tool utilizzabili dall'agente LangGraph.**
- **Tool disponibili**:
  - **`domanda_teoria`: tool avanzato per la gestione dei quiz teorici con funzionalità di ricerca e validazione**

### **src/services/database/**
- **QuizMongoDBService**: Servizio specializzato per la gestione dei quiz con metodi ottimizzati per le operazioni richieste dal tool `domanda_teoria`
- **MongoDBService**: Servizio generico per operazioni CRUD su MongoDB
- **Interface**: Definizioni di interfacce per i servizi database

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

### **tests/**
- **`tests/test_tools.py`**: Suite completa di test unitari per il tool `domanda_teoria` con mock completi
- **`tests/stream_query.py`**: Test end-to-end per l'endpoint di streaming
- **`tests/update_docs.py`**: Test end-to-end per l'aggiornamento documenti
- **`tests/conftest.py`**: Configurazione pytest e setup ambiente di test

## **Testing e Qualità del Codice**

### **Architettura dei Test**
- **Test Unitari**: Isolati dalle dipendenze esterne tramite mock completi
- **Test End-to-End**: Verificano l'integrazione completa del sistema
- **Mock Strategy**: Uso di `unittest.mock.Mock` e `patch` per isolare i componenti

### **Suite di Test del Tool domanda_teoria**
- **11 test** che coprono tutte le funzionalità
- **Mock completi** per `QuizMongoDBService` e `MongoDBService`
- **Test di validazione** per parametri di input
- **Test di gestione errori** per scenari edge
- **Test di formato output** per consistenza
- **Test di priorità parametri** per logica di business

### **Comandi di Test**
```bash
# Tutti i test
pytest -v -rs tests/

# Solo test unitari del tool
pytest -v -rs tests/test_tools.py

# Solo test E2E
pytest -v -rs tests/stream_query.py
pytest -v -rs tests/update_docs.py
```

## Configurazione

Per le variabili di ambiente, fare interamente riferimento al file `.env.example`.

## Deployment su Vercel Serverless

L'applicazione è ottimizzata per il deployment su **Vercel Serverless Environment** con le seguenti implementazioni specifiche:

### Gestione Event Loop
- **Creazione per-request**: Agente LangGraph e LLM creati ad ogni richiesta per evitare `Event loop is closed`
- **Checkpointer condiviso**: `InMemorySaver` condiviso a livello di processo per memoria volatile
- **Inizializzazione lazy**: Documenti e system prompt inizializzati solo quando necessario

### Ottimizzazioni Serverless
- **Memoria ibrida**: Volatile (InMemorySaver) + persistita (MongoDB) per gestire cold start
- **Serializzazione sicura**: Tutti gli output serializzati per compatibilità JSON
- **Gestione stati**: Thread-safe per richieste concorrenti
- **Resource cleanup**: Gestione corretta delle risorse in ambiente ephemeral
- **Tool Integration**: I tool sono progettati per essere compatibili con l'ambiente serverless

### Considerazioni Finali

- **Sicurezza**: Endpoint protetti da JWT Auth0.
- **Scalabilità**: Uso di cache locale per ridurre chiamate a servizi esterni, architettura stateless.
- **Estendibilità**: Modularità elevata, facile aggiungere endpoint, tool o provider LLM.
- **Persistenza**: Tutte le interazioni vengono salvate su MongoDB con serializzazione corretta.
- **Prompt Dinamico**: Il system prompt può essere aggiornato senza riavviare il servizio, aggiornando i file su S3 e chiamando `/api/update_docs`.
- **Tool Management**: **Gestione completa dei tool con streaming in tempo reale, persistenza dei risultati e tool specializzati per la gestione dei quiz.**
- **Serverless Ready**: Architettura ottimizzata per Vercel con gestione corretta di event loop e memoria.
- **Quality Assurance**: **Suite di test completa che garantisce la robustezza e manutenibilità del codice.**

## Gestione Event Loop in Ambiente Serverless

- **Problema risolto**: alla seconda richiesta consecutiva si verificava `Event loop is closed` durante lo streaming.
- **Soluzione implementata**:
  - Inizializzazione lazy di `combined_docs` e `system_prompt` (no oggetti async all'import).
  - Creazione dell'agente per-request: nuova istanza di modello e `create_react_agent(...)` dentro `ask()`.
  - Checkpointer condiviso a livello di processo (`InMemorySaver`) per mantenere memoria volatile tra richieste (finché il container resta caldo).
  - Memoria: se lo stato volatile del thread è vuoto, si esegue il seed dei `messages` da MongoDB (inclusi ToolMessage storici) e si aggiorna lo stato con `update_state(config, {...})`.
  - Gestione errori: intercettato `RuntimeError` nello streaming per segnalare chiaramente la condizione di event loop non disponibile.
  - Serializzazione tool: aggiunta `_serialize_tool_output()` per gestire tutti i tipi di output tool.

## Gestione Tool con Streaming

### Architettura Tool
- **Eventi monitorati**: `on_tool_end` per risultati tool, `on_chat_model_stream` per messaggi AI
- **Serializzazione**: `_serialize_tool_output()` gestisce ToolMessage, dict, primitive e conversioni generiche. Con la normalizzazione a livello `MongoDBService`, i risultati del tool sono già JSON-safe.
- **Streaming**: Tool results streamati in tempo reale come eventi `tool_result`. Per tool marcati `return_direct=True` lo stream si conclude dopo l'emissione del `tool_result`.
- **Persistenza**: Tool records salvati su MongoDB con struttura normalizzata

### **Tool domanda_teoria - Architettura e Implementazione**
- **Decoratore LangGraph**: `@tool` per integrazione con l'agente
- **Validazione Input**: Controlli robusti sui parametri (capitoli 1-10, testo minimo 3 caratteri)
- **Logica di Priorità**: Implementazione della gerarchia dei parametri per determinare l'operazione da eseguire
- **Gestione Errori**: Gestione completa di tutti gli scenari di errore con messaggi informativi
- **Formato Output**: Standardizzazione dell'output per consistenza e compatibilità
- **Integrazione Database**: Utilizzo ottimizzato di `QuizMongoDBService` per le operazioni sui quiz

### Flusso Tool
1. Agente decide di invocare tool
2. `on_tool_end` cattura risultato e lo serializza
3. Risultato streamato come `{"type": "tool_result", "tool_name": "...", "data": {...}, "final": true}` (dove `data.content` è un oggetto e non più una stringa JSON)
4. Risultato salvato in `tool_records` per persistenza
5. Se il tool è `return_direct`, l'agente termina l'elaborazione immediatamente dopo il `tool_result` e non vengono emessi ulteriori `agent_message`. Il salvataggio su MongoDB include il campo `tool` e, se non presente risposta testuale, un `system` eventualmente vuoto.

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
- src/tools.py
- **src/services/database/**
- src/logging_config.py
- src/test.py
- **tests/**

---

Per approfondimenti su una funzione specifica, consultare i file e le funzioni sopra elencate.
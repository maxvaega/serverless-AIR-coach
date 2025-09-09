# Analisi del Codebase AIR Coach API

## Panoramica Generale

AIR Coach API è un'applicazione basata su FastAPI progettata per gestire interazioni con un chatbot intelligente, deployata su ambiente serverless Vercel. L'applicazione utilizza un agente LangGraph prebuilt (ReAct) con modello Gemini 2.5 Flash di Google per generare risposte, con capacità di:
- caricare dinamicamente il contesto da file Markdown su AWS S3 (system prompt)
- invocare tool applicativi con gestione streaming dei risultati
- gestire memoria a breve termine tramite `InMemorySaver` (volatile, per istanza)
- ibridare la memoria con la cronologia persistita su MongoDB (fallback serverless)
- serializzare correttamente gli output dei tool per compatibilità JSON
- gestire quiz teorici tramite tool e retrieve su mongodb

## Struttura del Progetto

Il progetto è organizzato in un'architettura modulare con separazione delle responsabilità:

### **Moduli Core**
- **app.py**: Punto di ingresso dell'applicazione che definisce gli endpoint FastAPI
- **src/rag.py**: Orchestratore principale per RAG, ora snellito (95 righe vs 403 originali)
- **src/database.py**: Gestisce le interazioni con MongoDB
- **src/env.py**: Carica le variabili d'ambiente
- **src/logging_config.py**: Configura il sistema di logging
- **src/models.py**: Definisce i modelli Pydantic per la validazione dei dati
- **src/tools.py**: Implementa i tool utilizzabili dall'agente LangGraph
- **src/test.py**: Script per testare localmente le funzionalità

### **Nuova Architettura Modulare**
- **src/agent/**: Moduli specializzati per la gestione degli agenti LangGraph
  - `agent_manager.py`: Factory per creazione agenti configurati per-request
  - `streaming_handler.py`: Gestione eventi streaming e tool con output JSON formattato
  - `state_manager.py`: Gestione checkpointer e stato thread con pattern singleton
- **src/memory/**: Moduli per gestione memoria conversazionale
  - `seeding.py`: Logica unificata per seeding memoria da MongoDB (elimina duplicazione)
  - `persistence.py`: Gestione persistenza conversazioni e logging completamento run

### **Test Suite Completa**
- **tests/**: Suite completa di test unitari e end-to-end
  - Test unitari: 12/12 passati ✅
  - Test E2E: 6/6 passati ✅ (update_docs + stream_query completi)

## Funzionalità Principali

### 1. Gestione del Contesto da AWS S3

L'applicazione carica dinamicamente il contesto per il modello LLM da file Markdown archiviati in un bucket AWS S3:

- Caricamento iniziale: All'avvio dell'applicazione, i file Markdown vengono scaricati e combinati
- Caching: Il contenuto combinato viene memorizzato in cache per migliorare le prestazioni
- Aggiornamento manuale: Un endpoint dedicato permette di forzare l'aggiornamento della cache

### 2. Interazione con LangGraph (LLM + Tool + Memoria) - Architettura Refactorizzata

#### **Gestione Agenti (src/agent/)**
- **AgentManager**: Factory pattern per creazione agenti per-request con configurazione unificata
- **Agente**: `create_react_agent` con `prompt=personalized_prompt`, `pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT)` e `tools=[domanda_teoria]`
- **StreamingHandler**: Gestione dedicata eventi streaming con parsing JSON corretto e serializzazione tool

#### **Gestione Memoria (src/memory/)**
- **MemorySeeder**: Logica unificata per seeding memoria da MongoDB (elimina duplicazione codice)
- **ConversationPersistence**: Persistenza conversazioni e logging strutturato
- **Memoria ibrida (serverless‑friendly)**:
  - Volatile: `InMemorySaver` gestito via `AgentStateManager` singleton
  - Persistita: MongoDB con seeding automatico in cold start
- **thread_id versionato**: `f"{userid}:v{prompt_version}"` per isolamento memoria tra versioni prompt

#### **Streaming e Tool**
- **Streaming**: Gestione asincrona SSE con `StreamingHandler` dedicato
- **Tool processing**: Eventi `on_tool_end`/`on_chat_model_stream` gestiti separatamente
- **JSON formatting**: Correzione parsing con rimozione escape sequences `\\n\\n`
- **Serializzazione**: Output JSON-compatibile con `_serialize_tool_output`
- **Persistenza**: Salvataggio automatico risultati tool su MongoDB

#### **Finestra Conversazionale**
- **Warm path**: Nessun trimming, stato completo mantenuto
- **Cold start**: Seeding limitato da DB, finestra LLM via `pre_model_hook`
- **Coerenza**: `llm_input_messages` limita input senza modificare `messages` stato

### 2.b Gestione Funzionale del System Prompt (versionato)

- Il system prompt dell'agente è gestito in modo centralizzato e versionato.
- Quando il prompt viene aggiornato, le conversazioni successive utilizzano automaticamente la versione più recente, senza aumentare la latenza della richiesta.
- La memoria conversazionale è isolata per versione del prompt: le nuove richieste proseguono su un contesto distinto rispetto alle versioni precedenti, evitando mescolamenti.

### 3. Gestione Tool con Streaming

- **Tool Execution**: I tool vengono eseguiti dall'agente e i loro risultati sono streamati in tempo reale
- **Serializzazione**: Gli output dei tool (inclusi ToolMessage) vengono serializzati correttamente per compatibilità JSON
- **Persistenza**: I risultati dei tool vengono salvati su MongoDB insieme alla conversazione
- **History Management**: I tool storici vengono ricostruiti come ToolMessage durante il seeding della memoria

### 4. **Tool Quiz Management - domanda_teoria**

Il tool `domanda_teoria` fornisce funzionalità avanzate per la gestione dei quiz teorici:

- **Domande Casuali**: Recupero di domande casuali da tutto il database o da capitoli specifici (1-10)
- **Domande Specifiche**: Ricerca di domande per numero e capitolo esatti
- **Ricerca Testuale**: Ricerca fuzzy case-insensitive nel testo delle domande
- **Validazione Input**: Controllo dei parametri (capitoli validi, testo minimo)
- **Gestione Errori**: Gestione robusta di database vuoto, capitoli non validi, domande non trovate
- **Formato Output**: Output strutturato e consistente per tutte le operazioni

**Parametri di Input:**
- `capitolo`: Numero del capitolo (1-10)
- `domanda`: Numero specifico della domanda
- `testo`: Stringa di ricerca testuale (minimo 3 caratteri)

**Priorità Parametri:**
1. `testo` (ricerca testuale)
2. `capitolo` + `domanda` (domanda specifica)
3. `capitolo` (domanda casuale dal capitolo)
4. Nessun parametro (domanda casuale globale)

## Endpoint API

### 1. /api/stream_query
- Metodo: POST
- Descrizione: Elabora una query e restituisce una risposta in streaming (SSE)
- Parametri:
  - message: Il testo della query
  - userid: L'ID dell'utente
- Autenticazione: Richiede Bearer JWT (Auth0)
- Streaming Response:
  - `{"type": "agent_message", "data": "testo"}`: Messaggi dell'agente AI
  - `{"type": "tool_result", "tool_name": "nome", "data": {...}, "final": true}`: Risultati dei tool
- Persistenza: al termine del turno salva su MongoDB la tripletta `human`/`system`/`tool` (se presente). Il campo `tool` include nome tool e risultato serializzato.

### 2. /api/update_docs
- Metodo: POST
- Descrizione: Forza l'aggiornamento della cache dei documenti da S3 e salva il system prompt su S3
- Autenticazione: Attualmente pubblico

## Autenticazione

- /api/stream_query: Richiede token Bearer JWT valido emesso da Auth0. La verifica avviene tramite JWKS (classe `VerifyToken` in `src/auth.py`) con audience e issuer configurati.
- /api/update_docs: Endpoint pubblico (nessuna autenticazione).

## Modelli di Dati

### MessageRequest
```python
class MessageRequest(BaseModel):
    message: str
    userid: str = Field(..., min_length=1)

### MessageResponse
class MessageResponse(BaseModel):
    query: str
    result: str
    userid: str = Field(..., min_length=1)

## **Testing e Qualità del Codice**

### **Test End-to-End**
- **`tests/stream_query.py`**: Test dell'endpoint di streaming con autenticazione
- **`tests/update_docs.py`**: Test dell'aggiornamento documenti
- **`tests/conftest.py`**: Configurazione pytest e setup ambiente

### **Test Unitari Completati**
- **`tests/test_tools.py`**: Suite completa per il tool `domanda_teoria`
  - 11 test che coprono tutte le funzionalità
  - Mock completi per isolare i test dalle dipendenze esterne
  - Test di validazione, gestione errori e formato output
  - Copertura completa dei casi edge e scenari di errore

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

Fare riferimento esclusivamente al file `.env.example` per l'elenco completo delle variabili di ambiente da impostare.

## Meccanismi di Sicurezza e Prestazioni

- CORS: Configurato per consentire richieste cross-origin da development
- Caching: Implementato per i documenti S3 per migliorare le prestazioni
- Lock di threading: Utilizzato per sincronizzare gli aggiornamenti manuali dei documenti
- Gestione delle eccezioni: Implementata negli endpoint
- Logging: Sistema di logging configurato per monitorare l'applicazione
- Tool - Validazione Input: Controlli robusti sui parametri dei tool per prevenire errori

## Flusso di Elaborazione delle Query (streaming) - Architettura Refactorizzata

### **Pipeline di Richiesta Modulare**
1. **Ricezione**: L'utente invia query a `/api/stream_query` (JWT richiesto)
2. **Inizializzazione Agente**: `AgentManager.create_agent()` crea agente per-request con:
   - Prompt personalizzato da documenti S3 + metadati utente
   - Checkpointer condiviso via `AgentStateManager.get_checkpointer()`
   - Configurazione thread versionata: `thread_id = f"{userid}:v{prompt_version}"`

### **Gestione Memoria Ibrida (src/memory/)**
3. **Memory Seeding**: `MemorySeeder.seed_agent_memory()` gestisce:
   - **Warm path**: Riutilizzo memoria volatile esistente
   - **Cold start**: Ricostruzione cronologia da MongoDB con supporto `ToolMessage`
   - **Seeding unificato**: Eliminazione duplicazione logica tra sync/async

### **Elaborazione Streaming (src/agent/)**
4. **Streaming Handler**: `StreamingHandler.handle_stream_events()` processa:
   - **Eventi Tool**: `on_tool_end` → serializzazione e streaming `tool_result`  
   - **Eventi AI**: `on_chat_model_stream` → streaming `agent_message`
   - **JSON Parsing**: Correzione formato con rimozione escape sequences
   - **Tool Quiz**: `domanda_teoria` per gestione quiz con output strutturato

### **Persistenza e Completamento**
5. **Salvataggio**: `ConversationPersistence.save_conversation()`:
   - Tripletta `human`/`system`/`tool` su MongoDB
   - Logging strutturato completamento run
   - Gestione fallback per risposte vuote

## Deployment - Ottimizzazioni Serverless Refactorizzate

L'applicazione è progettata per il deployment su Vercel Serverless Environment con architettura modulare ottimizzata:

### **Gestione Agenti Serverless**
- **AgentManager**: Creazione per-request con factory pattern per evitare event loop chiuso
- **AgentStateManager**: Singleton per checkpointer condiviso thread-safe
- **Configurazione isolata**: Thread versionati per isolamento memoria tra versioni prompt

### **Memoria Ibrida Ottimizzata**
- **MemorySeeder**: Logica unificata seeding elimina duplicazione e riduce cold start
- **Persistenza intelligente**: MongoDB fallback con ricostruzione `ToolMessage` storici
- **Cache management**: Gestione ottimizzata risorse volatile/persistite

### **Streaming Performance**
- **StreamingHandler**: Gestione dedicata eventi con parsing JSON ottimizzato
- **Serializzazione sicura**: Output JSON-compatibile garantito per compatibilità serverless
- **Tool Integration**: Architettura modulare compatibile ambiente ephemeral

## Conclusioni

AIR Coach API è un'applicazione che implementa un sistema di chatbot con **architettura modulare refactorizzata** per funzionalità di caricamento del contesto da S3 e **gestione avanzata dei quiz teorici**. 

### **Miglioramenti Architetturali**
- **Modularità**: Da 1 file monolitico (403 righe) a 6 moduli specializzati (75% riduzione codice)
- **Separazione responsabilità**: `src/agent/` e `src/memory/` per gestione dedicata
- **Eliminazione duplicazione**: Logica unificata seeding e streaming
- **Manutenibilità**: Codice più leggibile e testabile

### **Tecnologie e Performance**
L'uso di tecnologie moderne come **FastAPI**, **MongoDB**, **AWS S3** e **LangGraph** con architettura modulare la rendono scalabile e manutenibile. Le funzionalità di streaming ottimizzate e la gestione della cronologia delle chat migliorano l'esperienza utente, mentre il sistema di caching e la gestione memoria ibrida ottimizzano le prestazioni serverless.

### **Qualità e Robustezza**
**La suite di test completa (18/18 test passati) garantisce la qualità del codice e la robustezza delle funzionalità implementate**, con copertura completa per unit test dei tool e test E2E degli endpoint.

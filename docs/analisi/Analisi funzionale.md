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

Il progetto è organizzato in diversi moduli:

- app.py: Punto di ingresso dell'applicazione che definisce gli endpoint FastAPI
- src/rag.py: Implementa la logica di Retrieval Augmented Generation (RAG) e l'interazione con il modello LLM
- src/database.py: Gestisce le interazioni con MongoDB
- src/env.py: Carica le variabili d'ambiente
- src/logging_config.py: Configura il sistema di logging
- src/models.py: Definisce i modelli Pydantic per la validazione dei dati
- src/tools.py: Implementa i tool utilizzabili dall'agente LangGraph, incluso il tool domanda_teoria per la gestione dei quiz
- src/test.py: Script per testare localmente le funzionalità
- tests/: Suite completa di test unitari e end-to-end

## Funzionalità Principali

### 1. Gestione del Contesto da AWS S3

L'applicazione carica dinamicamente il contesto per il modello LLM da file Markdown archiviati in un bucket AWS S3:

- Caricamento iniziale: All'avvio dell'applicazione, i file Markdown vengono scaricati e combinati
- Caching: Il contenuto combinato viene memorizzato in cache per migliorare le prestazioni
- Aggiornamento manuale: Un endpoint dedicato permette di forzare l'aggiornamento della cache

### 2. Interazione con LangGraph (LLM + Tool + Memoria)

- Agente: `create_react_agent` con `prompt=system_prompt` e `tools=[domanda_teoria]`.
- Memoria (serverless‑friendly):
  - Volatile: `InMemorySaver` (presente finché l'istanza è "calda").
  - Persistita: MongoDB (cronologia utente). Se la memoria volatile è assente, la cronologia viene letta da DB e "seedata" nella memoria volatile del thread.
- `thread_id`: per utente (passato via `config`), un thread per utente.
- Streaming: risposte in streaming asincrone (SSE) con gestione separata di tool e messaggi AI.
- Tool: il risultato dei tool viene streamato in tempo reale con serializzazione JSON-compatibile e salvato su DB al termine.

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

## Flusso di Elaborazione delle Query (streaming)

- L'utente invia una query a `/api/stream_query` (JWT richiesto).
- L'agente LangGraph è inizializzato con `prompt` dai documenti S3.
- Memoria ibrida:
  - Si tenta di leggere la memoria volatile del thread (InMemorySaver) tramite `thread_id=userid`.
  - Se vuota (es. cold start serverless), si ricostruisce la cronologia dagli ultimi messaggi in MongoDB, inclusi eventuali risultati `tool`, e la si inserisce nella memoria volatile.
- L'invocazione del turno passa solo il messaggio corrente; la memoria del thread fornisce lo storico.
- L'agente può decidere di usare i tool:
  - Tool Quiz: L'agente può utilizzare `domanda_teoria` per recuperare informazioni sui quiz
  - Eventi on_tool_end catturano i risultati e li streamano come tool_result
  - Eventi on_chat_model_stream streamano i messaggi AI come agent_message
- A fine turno, si salva su MongoDB la tripletta `human`/`system`/`tool`.

## Deployment
L'applicazione è progettata per il deployment su Vercel Serverless Environment con le seguenti considerazioni:

- Creazione dell'agente per-request per evitare problemi di event loop chiuso
- Gestione memoria ibrida per persistenza tra cold start
- Serializzazione JSON-compatibile per tutti gli output
- Gestione ottimizzata delle risorse serverless
- Tool Integration: I tool sono progettati per essere compatibili con l'ambiente serverless

## Conclusioni

AIR Coach API è un'applicazione che implementa un sistema di chatbot con funzionalità di caricamento del contesto da S3 e **gestione avanzata dei quiz teorici**. L'architettura modulare e l'uso di tecnologie moderne come FastAPI, MongoDB, AWS S3 e **LangGraph** la rendono scalabile e manutenibile. Le funzionalità di streaming e la gestione della cronologia delle chat migliorano l'esperienza utente, mentre il sistema di caching ottimizza le prestazioni. **La suite di test completa garantisce la qualità del codice e la robustezza delle funzionalità implementate.**

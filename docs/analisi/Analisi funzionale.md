# Analisi del Codebase AIR Coach API

## Panoramica Generale

AIR Coach API è un'applicazione basata su FastAPI progettata per gestire interazioni con un chatbot intelligente. L'applicazione utilizza un agente LangGraph prebuilt (ReAct) con modello Gemini 2.0 di Google per generare risposte, con capacità di:
- caricare dinamicamente il contesto da file Markdown su AWS S3 (system prompt)
- invocare tool applicativi
- gestire memoria a breve termine tramite `InMemorySaver` (volatile, condivisa a livello di processo/istanza server: persiste tra richieste finché il container resta "caldo")
- ibridare la memoria con la cronologia persistita su MongoDB (fallback serverless)

## Struttura del Progetto

Il progetto è organizzato in diversi moduli:

- app.py: Punto di ingresso dell'applicazione che definisce gli endpoint FastAPI
- src/rag.py: Implementa la logica di Retrieval Augmented Generation (RAG) e l'interazione con il modello LLM
- src/database.py: Gestisce le interazioni con MongoDB
- src/env.py: Carica le variabili d'ambiente
- src/logging_config.py: Configura il sistema di logging
- src/models.py: Definisce i modelli Pydantic per la validazione dei dati
- src/test.py: Script per testare localmente le funzionalità

## Funzionalità Principali

### 1. Gestione del Contesto da AWS S3

L'applicazione carica dinamicamente il contesto per il modello LLM da file Markdown archiviati in un bucket AWS S3:

- Caricamento iniziale: All’avvio dell’applicazione, i file Markdown vengono scaricati e combinati
- Caching: Il contenuto combinato viene memorizzato in cache per migliorare le prestazioni
- Aggiornamento manuale: Un endpoint dedicato permette di forzare l’aggiornamento della cache

### 2. Interazione con LangGraph (LLM + Tool + Memoria)

- Agente: `create_react_agent` con `prompt=system_prompt` e `tools=[test_licenza]`.
- Memoria (serverless‑friendly):
  - Volatile: `InMemorySaver` condiviso a livello di processo (presente finché l’istanza è “calda”).
  - Persistita: MongoDB (cronologia utente). Se la memoria volatile è assente, la cronologia viene letta da DB e “seedata” nella memoria volatile del thread.
- `thread_id`: per utente (passato via `config`), un thread per utente.
  - Streaming: risposte in streaming asincrone (SSE) con buffering guidato dagli eventi:
    - Se l’agente NON usa tool, la risposta viene streammata normalmente (flush del buffer pre‑tool alla fine del run).
    - Se l’agente usa un tool, eventuali token “pre‑tool” (preamboli) vengono scartati e si streammano solo i token “post‑tool” (risultato finale coerente).
    - Opzionale: i tool possono emettere progress via stream "custom".
- Tool: il risultato dei tool viene reso disponibile al modello all’interno del turno corrente e salvato su DB al termine.

## Endpoint API

### 1. /api/stream_query
- Metodo: POST
- Descrizione: Elabora una query e restituisce una risposta in streaming (SSE)
- Parametri:
  - message: Il testo della query
  - userid: L’ID dell’utente
- Autenticazione: Richiede Bearer JWT (Auth0)
 - Persistenza: al termine del turno salva su MongoDB la tripletta `human`/`system`/`tool` (se presente). Il campo `tool` include nome tool e risultato.

### 2. /api/update_docs
- Metodo: POST
- Descrizione: Forza l’aggiornamento della cache dei documenti da S3 e salva il system prompt su S3
- Autenticazione: Attualmente pubblico

## Autenticazione

- /api/stream_query: Richiede token Bearer JWT valido emesso da Auth0. La verifica avviene tramite JWKS (classe `VerifyToken` in `src/auth.py`) con audience e issuer configurati.
- /api/update_docs: Endpoint pubblico (nessuna autenticazione).

## Modelli di Dati

### MessageRequest
class MessageRequest(BaseModel):
- message: str
- userid: str = Field(..., min_length = 1)

### MessageResponse
class MessageResponse(BaseModel):
- query: str
- result: str
- userid: str = Field(..., min_length = 1)

## Configurazione

Fare riferimento esclusivamente al file `.env.example` per l’elenco completo delle variabili di ambiente da impostare.

## Meccanismi di Sicurezza e Prestazioni

- CORS: Configurato per consentire richieste cross-origin da development
- Caching: Implementato per i documenti S3 per migliorare le prestazioni
- Lock di threading: Utilizzato per sincronizzare gli aggiornamenti manuali dei documenti
- Gestione delle eccezioni: Implementata negli endpoint
- Logging: log sintetici e strutturati (thread_id, durata, response_len, presenza tool, anteprima troncata) per monitoraggio e diagnosi; contenuti testuali completi non vengono più loggati.

## Flusso di Elaborazione delle Query (streaming)

- L’utente invia una query a `/api/stream_query` (JWT richiesto).
- L’agente LangGraph è inizializzato con `prompt` dai documenti S3.
- Memoria ibrida:
  - Si tenta di leggere la memoria volatile del thread (InMemorySaver) tramite `thread_id=userid`.
  - Se vuota (es. cold start serverless), si ricostruisce la cronologia dagli ultimi messaggi in MongoDB, inclusi eventuali risultati `tool`, e la si inserisce nella memoria volatile.
- L’invocazione del turno passa solo il messaggio corrente; la memoria del thread fornisce lo storico.
- L’agente può decidere di usare i tool e produce la risposta in streaming.
- A fine turno, si salva su MongoDB la tripletta `human`/`system`/`tool`.

## Conclusioni

AIR Coach API è un’applicazione che implementa un sistema di chatbot con funzionalità di caricamento del contesto da S3. L’architettura modulare e l’uso di tecnologie moderne come FastAPI, MongoDB e AWS S3 la rendono scalabile e manutenibile. Le funzionalità di streaming e la gestione della cronologia delle chat migliorano l’esperienza utente, mentre il sistema di caching ottimizza le prestazioni.

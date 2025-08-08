# Analisi del Codebase AIR Coach API

## Panoramica Generale

AIR Coach API è un'applicazione basata su FastAPI progettata per gestire interazioni con un chatbot intelligente. L'applicazione utilizza il modello Gemini 2.0 Flash di Google per generare risposte alle query degli utenti, con la capacità di caricare dinamicamente il contesto da file Markdown archiviati in AWS S3.

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

### 2. Interazione con il Modello LLM

L’applicazione utilizza il modello Gemini 2.0 Flash di Google per generare risposte:

- Prompt di sistema: Costruito utilizzando il contenuto combinato dei documenti
- Cronologia delle chat: Per lo streaming è sempre attiva (ultimi 10 messaggi)
- Streaming: Supporta risposte in streaming asincrone

## Endpoint API

### 1. /api/stream_query
- Metodo: POST
- Descrizione: Elabora una query e restituisce una risposta in streaming (SSE)
- Parametri:
  - message: Il testo della query
  - userid: L’ID dell’utente
- Autenticazione: Richiede Bearer JWT (Auth0)

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
- Logging: Sistema di logging configurato per monitorare l’applicazione

## Flusso di Elaborazione delle Query

- L’utente invia una query tramite /api/stream_query
- L’applicazione carica il contesto dai documenti S3 (se non già in cache)
- Recupera la cronologia delle chat (sempre attiva per lo stream, ultimi 10 messaggi)
- Costruisce un prompt di sistema utilizzando il contesto e la cronologia
- Invia il prompt al modello Gemini 2.0 Flash
- Riceve e restituisce la risposta in streaming
- Salva la conversazione in MongoDB

## Conclusioni

AIR Coach API è un’applicazione che implementa un sistema di chatbot con funzionalità di caricamento del contesto da S3. L’architettura modulare e l’uso di tecnologie moderne come FastAPI, MongoDB e AWS S3 la rendono scalabile e manutenibile. Le funzionalità di streaming e la gestione della cronologia delle chat migliorano l’esperienza utente, mentre il sistema di caching ottimizza le prestazioni.

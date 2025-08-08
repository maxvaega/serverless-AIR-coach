# Analisi del Codebase AIR Coach API

## Panoramica Generale

AIR Coach API è un'applicazione basata su FastAPI progettata per gestire interazioni con un chatbot intelligente. L'applicazione utilizza il modello Gemini 2.0 Flash di Google per generare risposte alle query degli utenti, con la capacità di caricare dinamicamente il contesto da file Markdown archiviati in AWS S3.

## Struttura del Progetto

Il progetto è organizzato in diversi moduli:

-   app.py: Punto di ingresso dell'applicazione che definisce gli endpoint FastAPI

-   src/rag.py: Implementa la logica di Retrieval Augmented Generation (RAG) e l'interazione con il modello LLM

-   src/database.py: Gestisce le interazioni con MongoDB

-   src/env.py: Carica le variabili d'ambiente

-   src/logging_config.py: Configura il sistema di logging

-   src/models.py: Definisce i modelli Pydantic per la validazione dei dati

-   src/test.py: Script per testare localmente le funzionalità

## Funzionalità Principali

### 1. Gestione del Contesto da AWS S3

L'applicazione carica dinamicamente il contesto per il modello LLM da file Markdown archiviati in un bucket AWS S3:

-   Caricamento iniziale: All'avvio dell'applicazione, i file Markdown vengono scaricati e combinati

-   Caching: Il contenuto combinato viene memorizzato in cache per migliorare le prestazioni

-   Aggiornamento manuale: Un endpoint dedicato permette di forzare l'aggiornamento della cache

### 2. Interazione con il Modello LLM

L'applicazione utilizza il modello Gemini 2.0 Flash di Google per generare risposte:

-   Prompt di sistema: Costruito utilizzando il contenuto combinato dei documenti

-   Cronologia delle chat: Opzionalmente include la cronologia delle conversazioni precedenti

-   Streaming: Supporta sia risposte sincrone che streaming asincrono

### 3. Persistenza dei Dati

Le conversazioni vengono archiviate in MongoDB:

-   Memorizzazione delle query: Ogni query e risposta viene salvata con timestamp e ID utente

-   Recupero della cronologia: Le conversazioni precedenti possono essere recuperate per contesto

## Endpoint API

L'applicazione espone i seguenti endpoint:

### 1.  /api/

-   Metodo: GET

-   Descrizione: Endpoint di benvenuto

-   Risposta: Messaggio di benvenuto

### 2.  /api/query

-   Metodo: POST

-   Descrizione: Elabora una query e restituisce una risposta sincrona

-   Parametri:

-   message: Il testo della query

-   userid: L'ID dell'utente

-   Risposta: Oggetto MessageResponse contenente la query originale, il risultato e l'ID utente

### 3.  /api/stream_query

-   Metodo: POST

-   Descrizione: Elabora una query e restituisce una risposta in streaming

-   Parametri:

-   message: Il testo della query

-   userid: L'ID dell'utente

-   Risposta: Stream di eventi SSE (Server-Sent Events)

### 4.  /api/update_docs

-   Metodo: POST

-   Descrizione: Forza l'aggiornamento della cache dei documenti da S3

-   Risposta: Informazioni sui documenti aggiornati, inclusi conteggio e dettagli

### 5.  /api/test/

-   Metodo: POST

-   Descrizione: Endpoint di test per verificare la funzionalità base

-   Parametri:

-   message: Il testo della query

-   userid: L'ID dell'utente

-   Risposta: Eco del messaggio ricevuto

## Modelli di Dati

### MessageRequest

class  MessageRequest(BaseModel):

message: str

userid: str = Field(..., min_length = 1)

### MessageResponse

class  MessageResponse(BaseModel):

query: str

result: str

userid: str = Field(..., min_length = 1)

## Configurazione

L'applicazione richiede le seguenti variabili d'ambiente:

-   Google AI: GOOGLE_API_KEY

-   MongoDB: MONGODB_URI, DATABASE_NAME, COLLECTION_NAME

-   AWS S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME

## Meccanismi di Sicurezza e Prestazioni

-   CORS: Configurato per consentire richieste cross-origin

-   Caching: Implementato per i documenti S3 per migliorare le prestazioni

-   Lock di threading: Utilizzato per sincronizzare gli aggiornamenti manuali dei documenti

-   Gestione delle eccezioni: Implementata in tutti gli endpoint

-   Logging: Sistema di logging configurato per monitorare l'applicazione

## Flusso di Elaborazione delle Query

-   L'utente invia una query tramite  /api/query o /api/stream_query

-   L'applicazione carica il contesto dai documenti S3 (se non già in cache)

-   Se richiesto, recupera la cronologia delle chat da MongoDB

-   Costruisce un prompt di sistema utilizzando il contesto e la cronologia

-   Invia il prompt al modello Gemini 2.0 Flash

-   Riceve e restituisce la risposta (in modo sincrono o in streaming)

-   Salva la conversazione in MongoDB

## Conclusioni

AIR Coach API è un'applicazione ben strutturata che implementa un sistema di chatbot avanzato con funzionalità RAG. L'architettura modulare e l'uso di tecnologie moderne come FastAPI, MongoDB e AWS S3 la rendono scalabile e manutenibile. Le funzionalità di streaming e la gestione della cronologia delle chat migliorano l'esperienza utente, mentre il sistema di caching ottimizza le prestazioni.
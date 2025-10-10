# Analisi Endpoint `/stream_query` - Prospettiva Client

## =� Richiesta HTTP

### **Endpoint**
```
POST /api/stream_query
```

### **Headers Richiesti**
```http
Authorization: Bearer <JWT_TOKEN_AUTH0>
Content-Type: application/json
Accept: text/event-stream
```

### **Body (JSON)**
```json
{
  "message": "string",    // Query utente (required)
  "userid": "string"      // ID utente, min_length=1 (required)
}
```

### **Codici di Risposta**
- **200**: Stream avviato con successo
- **401/403**: Token non valido o mancante
- **422**: Payload non valido (userid mancante o message vuoto)
- **500**: Errore interno del server

---

## <
 Caratteristiche dello Stream SSE

### **Formato**: Server-Sent Events (SSE)
- **Media Type**: `text/event-stream`
- **Encoding**: UTF-8
- **Protocollo**: SSE standard con prefisso `data:`

### **Struttura degli Eventi**

Lo stream produce eventi JSON strutturati in **3 tipi**:

#### **1. Agent Message (Streaming Testuale)**
Chunk incrementali della risposta dell'agente AI:

```json
data: {
  "type": "agent_message",
  "data": "Ciao! Sono"
}

data: {
  "type": "agent_message",
  "data": " AIR Coach,"
}

data: {
  "type": "agent_message",
  "data": " il tuo assistente virtuale."
}
```

**Caratteristiche**:
- Eventi multipli che si concatenano per formare la risposta completa
- Prodotti da `on_chat_model_stream` (streaming del modello LLM)
- Riferimento: [streaming_handler.py:117-128](../src/agent/streaming_handler.py#L117-L128)

#### **2. Tool Start (Opzionale - Attualmente Disabilitato)**
```json
data: {
  "type": "tool_start",
  "tool_name": "domanda_teoria",
  "input": {...}
}
```

**Note**:
- Codice presente ma **commentato** in [streaming_handler.py:78-84](../src/agent/streaming_handler.py#L78-L84)
- Non viene attualmente inviato al client

#### **3. Tool Result (Risultato Esecuzione Tool)**
```json
data: {
  "type": "tool_result",
  "tool_name": "domanda_teoria",
  "data": {
    "domanda": "Qual � la differenza tra...",
    "opzioni": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "risposta_corretta": "B"
  },
  "final": true
}
```

**Caratteristiche**:
- Singolo evento per tool eseguito
- `data` contiene l'output serializzato del tool
- Per `domanda_teoria`: output � JSON strutturato (non stringa)
- Campo `final: true` indica completamento tool
- Riferimento: [streaming_handler.py:91-115](../src/agent/streaming_handler.py#L91-L115)

---

## = Flusso di Eventi Tipico

### **Scenario 1: Risposta Testuale Pura**
```
1. data: {"type": "agent_message", "data": "Ciao!"}
2. data: {"type": "agent_message", "data": " Come"}
3. data: {"type": "agent_message", "data": " posso"}
4. data: {"type": "agent_message", "data": " aiutarti?"}
[STREAM CHIUSO]
```

### **Scenario 2: Esecuzione Tool + Risposta**
```
1. [Tool Start - non inviato, solo log server]
2. data: {"type": "tool_result", "tool_name": "domanda_teoria", "data": {...}, "final": true}
3. data: {"type": "agent_message", "data": "Ho"}
4. data: {"type": "agent_message", "data": " generato"}
5. data: {"type": "agent_message", "data": " una domanda per te."}
[STREAM CHIUSO]
```

---

## � Dettagli Tecnici Implementativi

### **Pipeline di Streaming**
1. **Entry Point**: [main.py:51-64](../src/main.py#L51-L64) - endpoint FastAPI
2. **Orchestratore**: [rag.py:123-159](../src/rag.py#L123-L159) - funzione `_ask_async()`
3. **Handler Eventi**: [streaming_handler.py:22-63](../src/agent/streaming_handler.py#L22-L63) - `StreamingHandler.handle_stream_events()`
4. **Fonte Eventi**: `agent_executor.astream_events()` con `version="v2"` (LangGraph)

### **Gestione Stato Interno**
Lo `StreamingHandler` mantiene:
- `response_chunks`: buffer dei chunk testuali ricevuti
- `tool_records`: registro tool eseguiti (per persistenza DB)
- `tool_executed`: flag booleano
- `serialized_output`: ultimo output tool serializzato

### **Post-Processing**
Al termine dello stream ([rag.py:139-157](../src/rag.py#L139-L157)):
1. Concatenazione risposta finale da `response_chunks`
2. Salvataggio conversazione su MongoDB con `ConversationPersistence`
3. Log metriche cache (se abilitato)

---

## <� Considerazioni per il Client

### **Parsing degli Eventi**
```javascript
// Esempio client-side (JavaScript)
const eventSource = new EventSource('/api/stream_query');

eventSource.onmessage = (event) => {
  const parsed = JSON.parse(event.data);

  switch(parsed.type) {
    case 'agent_message':
      appendTextToUI(parsed.data);  // Concatena chunk
      break;

    case 'tool_result':
      displayToolResult(parsed.tool_name, parsed.data);
      break;
  }
};
```

### **Gestione Errori**
- Timeout consigliato: **30 secondi** (vedi [test:94](../tests/stream_query.py#L94))
- Errori nello stream: `data: {"error": "..."}`
- Connessione persa: implementare retry logic

### **Edge Cases**
1. **Risposta vuota**: possibile se nessun chunk ricevuto e nessun tool eseguito (log warning ma no fallback, vedi [rag.py:145-153](../src/rag.py#L145-L153))
2. **Solo tool senza testo**: valido, riceverai solo eventi `tool_result`
3. **Multiple tool call**: ogni tool produce un evento `tool_result` separato

---

## =� Esempio Completo di Stream

```
// Request
POST /api/stream_query
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "message": "Generami una domanda sulla normativa ENAC",
  "userid": "google-oauth2|104612087445133776110"
}

// Response Stream
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {"type":"tool_result","tool_name":"domanda_teoria","data":{"domanda":"Secondo la normativa ENAC...","opzioni":["A) ...","B) ...","C) ...","D) ..."],"risposta_corretta":"B"},"final":true}

data: {"type":"agent_message","data":"Ho"}

data: {"type":"agent_message","data":" generato"}

data: {"type":"agent_message","data":" una"}

data: {"type":"agent_message","data":" domanda"}

data: {"type":"agent_message","data":" per"}

data: {"type":"agent_message","data":" te."}

[STREAM CLOSES]
```

---

## = Autenticazione

- **Metodo**: Auth0 JWT (via header `Authorization: Bearer <token>`)
- **Validazione**: [main.py:54](../src/main.py#L54) - `Security(auth.verify)`
- **Payload disponibile**: `auth_result` contiene `access_token`/`token`
- **Fallimento**: ritorna 401/403 prima dell'inizio dello stream

---

## =� Testing

Vedi [tests/stream_query.py](../tests/stream_query.py) per esempi completi di test E2E:
- `test_stream_query_success()`: Test streaming completo con token valido
- `test_stream_query_invalid_token()`: Test autenticazione fallita
- `test_stream_query_no_token()`: Test richiesta senza autenticazione
- `test_stream_query_invalid_payload_422()`: Test validazione payload

### **Esecuzione Test**
```bash
# Attiva ambiente virtuale
source /Users/massimoolivieri/Developer/serverless-AIR-coach/.venv/bin/activate

# Esegui tutti i test stream_query
pytest -v -rs tests/stream_query.py

# Con token configurato
TEST_AUTH_TOKEN="your-token-here" pytest -v -rs tests/stream_query.py
```

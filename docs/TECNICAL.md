# Technical Analysis - AIR Coach API

**Audience**: Developers, DevOps engineers, software architects
**Focus**: "HOW IT'S BUILT" (Engineering/DevOps perspective)

## Architecture Overview

AIR Coach API is a serverless application built on **FastAPI** with refactored modular architecture, deployed on **Vercel**. The system integrates **LangGraph** for AI agent management, **Google Gemini 2.5 Flash** as LLM model, **MongoDB** for persistence, and **AWS S3** for dynamic context loading.

### Key Architectural Characteristics

- **Modular architecture**: Responsibility separation into specialized modules
- **Serverless-friendly patterns**: Factory and Singleton for efficient resource management
- **Hybrid memory**: Combination of volatile and persistent memory
- **Event loop management**: Optimized for serverless environment
- **Google Cloud caching**: Configuration for implicit caching in European region

## Project Structure

### Entry Points and Configuration

```
├── run.py                          # Vercel deployment entry point
├── src/main.py                     # Main FastAPI application
├── src/env.py                      # Centralized Pydantic configuration
└── vercel.json                     # Deployment configuration
```

**Entry Point Separation:**
- `run.py`: Vercel serverless optimized entry point
- `src/main.py`: FastAPI application logic with endpoints and middleware
- Separation optimizes cold start and deployment configuration

### Refactored Modular Architecture

#### Core Modules
```
src/
├── main.py                         # FastAPI app + endpoint definitions
├── rag.py                          # Main orchestrator (95 lines vs 403 original)
├── models.py                       # Pydantic models (MessageRequest, MessageResponse)
├── auth.py                         # VerifyToken JWT Auth0
├── database.py                     # MongoDB CRUD operations
├── tools.py                        # LangGraph tools (domanda_teoria)
└── env.py                          # Pydantic Settings configuration
```

#### Specialized Modules

**`src/agent/` - Agent Management**
```
agent/
├── agent_manager.py                # AgentManager factory pattern
├── streaming_handler.py            # StreamingHandler for LangGraph events
└── state_manager.py                # AgentStateManager singleton checkpointer
```

**`src/memory/` - Memory Management**
```
memory/
├── seeding.py                      # MemorySeeder unified logic
└── persistence.py                  # ConversationPersistence MongoDB
```

**`src/monitoring/` - Monitoring & Cache**
```
monitoring/
└── cache_monitor.py                # Google Cloud cache metrics logging
```

**Support Modules**
```
src/
├── auth0.py                        # Auth0 metadata management
├── cache.py                        # In-memory caching (user/token)
├── utils.py                        # Utilities + PromptManager
├── s3_utils.py                     # AWS S3 operations
├── update_docs.py                  # Document refresh logic
├── prompt_personalization.py      # User prompt customization
├── history_hooks.py                # LLM input window management
└── services/database/              # Specialized database services
```

## Event Loop Architecture - Serverless Optimizations

### Problem Solved
**Original Issue**: `Event loop is closed` on second consecutive request in serverless environment.

### Modular Solution

#### 1. AgentManager (Factory Pattern)
```python
# src/agent/agent_manager.py
class AgentManager:
    @staticmethod
    def create_agent(user_id, token=None, user_data=False, checkpointer=None):
        # Per-request creation of LLM + create_react_agent()
        # Avoids reusing instances tied to event loop
```

**Characteristics:**
- Per-request creation of LLM and agent instances
- Isolated configuration for each request
- Lazy loading for documents/prompts without async objects

#### 2. AgentStateManager (Singleton Pattern)
```python
# src/agent/state_manager.py
class AgentStateManager:
    # Singleton for shared thread-safe InMemorySaver
    # Maintains volatile memory between requests (warm container)
```

**Functionality:**
- Process-level shared checkpointer
- Thread isolation per user/prompt version
- Memory persistence between requests in warm container

#### 3. MemorySeeder (Unified Seeding)
```python
# src/memory/seeding.py
class MemorySeeder:
    @staticmethod
    def seed_agent_memory(agent_executor, config, user_id, chat_history):
        # Unified logic for warm/cold path
        # Historical ToolMessage reconstruction from MongoDB
```

**Optimizations:**
- Elimination of seeding code duplication
- ToolMessage reconstruction support
- Atomic agent state updates

## Gestione Streaming e Tool

### StreamingHandler (Event Processing)
```python
# src/agent/streaming_handler.py
class StreamingHandler:
    async def handle_stream_events(self, agent_executor, query, config):
        # Gestione dedicata eventi streaming
        # JSON parsing ottimizzato
        # Tool output serialization
```

**Funzionalità chiave:**
- **Event monitoring**: `_handle_tool_end()` e `_handle_model_stream()`
- **JSON parsing fix**: Rimozione escape sequences `\\\\n\\\\n`
- **Serializzazione sicura**: Output JSON-compatibile garantito
- **Real-time streaming**: Eventi tool_result e agent_message

### Tool Processing Pipeline

#### domanda_teoria Tool
```python
# src/tools.py
@tool(return_direct=True)
def domanda_teoria(capitolo=None, domanda=None, testo=None) -> dict:
    # Tool LangGraph per quiz management
    # 4 modalità: casuale, per capitolo, specifica, ricerca testuale
```

**Architettura tool:**
- **LangGraph integration**: Decoratore `@tool` per agent
- **Validazione robusta**: Input validation e error handling
- **Priorità parametri**: Logica mutually exclusive
- **JSON output**: Struttura standardizzata per client

#### Flusso Tool Events
1. **Invocazione**: Agente decide di usare tool
2. **Event capture**: `StreamingHandler._handle_tool_end()`
3. **Serializzazione**: `_serialize_tool_output()` per JSON compatibility
4. **Streaming**: Event `{"type": "tool_result", "tool_name": "...", "data": {...}}`
5. **Return-direct handling**: Stream termina dopo tool_result se return_direct=True
6. **Persistenza**: `ConversationPersistence.save_conversation()`

## Gestione Memoria Ibrida

### Architettura Memoria
```
Memory Architecture:
├── Volatile (InMemorySaver)        # Process-level, warm container
├── Persistent (MongoDB)            # Cold start seeding + long-term storage
└── Rolling Window (pre_model_hook) # LLM input limiting
```

### Thread Management Versionato
```python
thread_id = f"{userid}:v{prompt_version}"
```
**Benefici:**
- Isolamento memoria tra versioni prompt diverse
- Compatibilità con aggiornamenti system prompt
- Prevenzione cross-contamination conversazioni

### Memory Seeding Strategy
```python
# Warm path: Riutilizzo memoria volatile esistente
# Cold start: Ricostruzione da MongoDB con HumanMessage/AIMessage/ToolMessage
# Finestra LLM: pre_model_hook limita a HISTORY_LIMIT senza modificare stato grafo
```

## Prompt Management e Versioning

### PromptManager (Process-Global)
```python
# src/utils.py
class PromptManager:
    current_system_prompt: str
    prompt_version: int
    # Thread-safe locking per aggiornamenti atomici
```

**Caratteristiche:**
- **Versioning**: Incremento intero per ogni aggiornamento
- **Atomic updates**: Swap sicuro con thread locking
- **Thread isolation**: `thread_id` versionato per isolamento memoria

### Prompt Personalization
```python
# src/prompt_personalization.py
def get_personalized_prompt_for_user(user_id, token, fetch_user_data):
    # Base prompt + metadati utente
    # No AIMessage injection, solo system prompt concatenation
```

**Implementazione:**
- Base prompt from S3 documents
- User metadata injection nel system prompt
- Cache user data (TTL 10 min)
- Thread ID generation con prompt version

## Google Cloud Caching Integration

### Configurazione Caching Implicito
```python
# src/env.py
VERTEX_AI_REGION = "europe-west8"    # Milano - EU compliance
ENABLE_GOOGLE_CACHING = True         # Automatic caching
CACHE_REGION = "europe-west8"        # Stessa region per max cache hits
```

### Cache Monitoring
```python
# src/monitoring/cache_monitor.py
def log_cache_metrics(response_metadata):
    # Estrazione metriche cache da response LLM
    # Logging cache hits/misses
    # Token savings tracking
```

**Funzionalità monitoring:**
- Cache effectiveness analysis
- Hit rate percentage tracking
- Request context logging per debugging
- Token savings calculation

## Database Architecture

### MongoDB Services
```
src/services/database/
├── database_quiz_service.py         # QuizMongoDBService specializzato
├── database_service.py              # MongoDBService generico
└── interface.py                     # Interface definitions
```

### Normalized Data Handling
```python
# MongoDBService garantisce output JSON-safe
# ObjectId → str, tuple/set → list
# Serializzazione automatica per compatibilità client
```

### Document Schema
```json
{
  "human": "domanda utente",
  "system": "risposta AI",
  "tool": {                          // opzionale
    "tool_name": "domanda_teoria",
    "data": {...}                    // output serializzato
  },
  "userId": "user_id",
  "timestamp": "ISO_datetime"
}
```

## Environment Management Refactorizzato

### Pydantic Settings Configuration
```python
# src/env.py
class Settings(BaseSettings):
    # LLM Configuration
    GOOGLE_API_KEY: str
    FORCED_MODEL: str = "models/gemini-2.5-flash"

    # Google Cloud Regional Configuration
    VERTEX_AI_REGION: str = "europe-west8"
    ENABLE_GOOGLE_CACHING: bool = True
    CACHE_DEBUG_LOGGING: bool = False

    # MongoDB, AWS, Auth0 configurations...
```

**Miglioramenti:**
- Type safety con Pydantic validation
- Categorizzazione logica configurazioni
- Backward compatibility con variabili globali
- Factory pattern con `@lru_cache()` singleton

## Testing Architecture

Per la documentazione completa sui test, consultare [`tests/readme.md`](../tests/readme.md).

### Test Strategy
- **Unit tests**: Mock completi per isolamento dipendenze
- **E2E tests**: Integrazione completa sistema
- **Tool tests**: Copertura completa funzionalità quiz
- **Performance tests**: Latenza e throughput

## Deployment Vercel - Ottimizzazioni Serverless

### Configurazione Deployment
```json
// vercel.json
{
  "functions": {
    "run.py": {
      "maxDuration": 30
    }
  }
}
```

### Entry Point Optimization
- **Separazione logica**: `run.py` (deployment) vs `src/main.py` (application)
- **Cold start optimization**: Lazy initialization documenti/prompt
- **Resource management**: Gestione efficiente memoria in ambiente ephemeral

### Serverless Optimizations
- **Event loop management**: Factory pattern per agent creation
- **Memory efficiency**: Singleton checkpointer + per-request agents
- **Performance**: 75% riduzione codice core (403→95 righe)
- **Caching strategy**: Local + Google Cloud + MongoDB hybrid

## Sicurezza e Monitoring

### Security Architecture
- **JWT verification**: Auth0 JWKS validation
- **Thread isolation**: Versioned thread IDs
- **Input validation**: Pydantic models + tool validation
- **Error handling**: Structured logging + fallback responses

### Monitoring Stack
- **Structured logging**: uvicorn logger standardizzato
- **Performance metrics**: Latenza, throughput, cache effectiveness
- **Error tracking**: Exception logging con context
- **Health checks**: `/api/test` endpoint

## Performance Considerations

### Scalability Factors
- **Concurrent requests**: Vercel function limits
- **Memory usage**: InMemorySaver + MongoDB hybrid
- **LLM rate limiting**: Google Gemini API quotas
- **Database connections**: MongoDB Atlas connection pooling

### Optimization Strategies
- **Caching layers**: Multiple level caching (local, cloud, database)
- **Lazy loading**: On-demand resource initialization
- **Connection reuse**: Process-level resource sharing
- **Regional optimization**: EU-based processing per compliance

## Riferimenti Architetturali

### Key Files per Architettura
- **`src/main.py`**: FastAPI application + endpoint logic
- **`run.py`**: Vercel entry point optimization
- **`src/rag.py`**: Orchestratore principale refactorizzato
- **`src/agent/agent_manager.py`**: Factory pattern per agenti
- **`src/memory/seeding.py`**: Unified memory seeding logic
- **`src/monitoring/cache_monitor.py`**: Cache performance monitoring

### Pattern Implementati
- **Factory Pattern**: AgentManager per creazione agenti
- **Singleton Pattern**: AgentStateManager per checkpointer
- **Strategy Pattern**: MemorySeeder per seeding unificato
- **Observer Pattern**: StreamingHandler per eventi
- **Template Method**: ConversationPersistence per salvataggio

### Considerazioni Future
- **Horizontal scaling**: Multi-region deployment potential
- **Performance monitoring**: Enhanced metrics collection
- **Security hardening**: Additional validation layers
- **Feature extensions**: New tool integration patterns
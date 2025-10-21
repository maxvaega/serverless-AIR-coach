from fastapi import FastAPI, HTTPException, APIRouter, Security
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
logger = logging.getLogger("uvicorn")
from src.models import MessageRequest
from src.rag import ask
from src.update_docs import update_docs
from src.s3_utils import create_prompt_file
from src.env import is_production
import json
import uvicorn
from src.auth import VerifyToken

auth = VerifyToken()

app = FastAPI(
    title='AIR Coach API',
    version='0.3',
    description='''
# AIR Coach API - Parachuting Theory Training Assistant

Intelligent AI-powered chatbot for parachuting license exam preparation and theoretical training.

## Overview

AIR Coach API provides real-time, context-aware educational support powered by **Google Gemini 2.5 Flash** and **LangGraph agents**. The system combines conversational AI with structured quiz management to deliver personalized learning experiences.

### Key Features

- **Real-time Streaming**: Server-Sent Events (SSE) for immediate feedback
- **Quiz Management**: Access to 10 chapters of parachuting theory exam questions
- **Persistent Memory**: Conversation history maintained across sessions
- **Personalized Responses**: User profile integration via Auth0
- **Dynamic Content**: Educational materials automatically loaded from AWS S3

### Technology Stack

- **Framework**: FastAPI (Python 3.7+)
- **AI Model**: Google Gemini 2.5 Flash
- **Agent Framework**: LangGraph with custom tools
- **Database**: MongoDB Atlas
- **Storage**: AWS S3
- **Authentication**: Auth0 JWT
- **Deployment**: Vercel Serverless

## Architecture & Best Practices

### Regional Configuration

- **Processing Region**: `europe-west8` (Milan, Italy)
- **EU Compliance**: All data processing within European region for GDPR compliance
- **Caching**: Google Cloud implicit caching enabled for improved performance

### Rate Limiting & Constraints

- **Function Timeout**: 30 seconds maximum (Vercel serverless limit)
- **Recommended Client Timeout**: 30 seconds
- **Concurrent Requests**: Subject to Vercel plan limits
- **LLM Rate Limits**: Google Gemini API quotas apply
- **Database Connections**: MongoDB Atlas connection pooling

### Memory Management

- **Thread Isolation**: Versioned thread IDs per user (`{userid}:v{prompt_version}`)
- **Rolling Window**: Last 10 messages sent to LLM (configurable via `HISTORY_LIMIT`)
- **Hybrid Persistence**: Volatile memory (warm containers) + MongoDB (cold start)
- **Cross-Session Memory**: Conversation history persisted and restored automatically

### Security

- **Authentication**: Auth0 JWT with JWKS validation
- **Token Validation**: Audience and issuer verification
- **Endpoint Protection**:
  - `/api/stream_query` - **Protected** (Auth0 required)
  - `/api/update_docs` - **Public**
  - `/api/test` - **Public**

## API Endpoints

### POST /api/stream_query

Main streaming chat endpoint with SSE response. See endpoint documentation for detailed usage.

**Protected**: Requires Auth0 Bearer token

### POST /api/update_docs

Manually refresh educational content cache from S3 and rebuild system prompt.

**Public**: No authentication required

### GET /api/test

Health check endpoint to verify API availability.

**Public**: No authentication required

## Client Integration Guide

### Authentication

All protected endpoints require an Auth0 JWT token:

```http
Authorization: Bearer <your_jwt_token>
```

Obtain tokens from your Auth0 application configuration.

### Error Handling Best Practices

- **401/403**: Token expired or invalid - refresh authentication
- **422**: Validation error - check request payload format
- **500**: Internal error - implement retry with exponential backoff (2s, 4s, 8s)
- **Timeout**: Connection timeout - retry up to 3 times

### Streaming Best Practices

1. **Set Appropriate Timeout**: Configure 30-second client timeout
2. **Handle Reconnection**: Implement retry logic for dropped connections
3. **Parse Events Incrementally**: Process SSE events as they arrive
4. **Concatenate Text Chunks**: Aggregate `agent_message` events for full response
5. **Close Connections**: Release resources when stream completes

### Example Integration

See `/api/stream_query` endpoint documentation for JavaScript and Python examples.

## Available Quiz Chapters

1. Meteorologia applicata al paracadutismo
2. Aerodinamica applicata al corpo in caduta libera
3. Tecnologia degli equipaggiamenti e strumenti in uso
4. Tecnica di direzione di lancio
5. Tecnica di utilizzo dei paracadute plananti
6. Elementi e procedure generali di sicurezza
7. Elementi e procedure di sicurezza nel lavoro relativo in caduta libera
8. Elementi e procedure di sicurezza nel volo in formazione con paracadute planante
9. Procedure in situazioni di emergenza
10. Normativa aeronautica attinente il paracadutismo

## Performance Considerations

### Optimization Strategies

- **Multi-level Caching**: Local cache + Google Cloud cache + MongoDB
- **Regional Processing**: EU-based inference for lower latency
- **Lazy Loading**: On-demand resource initialization
- **Connection Reuse**: Process-level resource sharing in warm containers

### Monitoring

- **Structured Logging**: All events and errors logged with context
- **Health Checks**: Use `/api/test` for availability monitoring
- **Performance Metrics**: Latency and throughput tracking
- **Cache Effectiveness**: Google Cloud cache hit/miss monitoring

## Support & Documentation

- **Interactive Docs**: [/api/docs](/api/docs) - Swagger UI with live testing
- **ReDoc**: [/api/redoc](/api/redoc) - Alternative documentation interface
- **Source Code**: [GitHub Repository](https://github.com/maxvaega/serverless-AIR-coach)

For issues or feature requests, please contact the development team.
    ''',
    docs_url="/api/docs",  # Swagger enabled in production
    redoc_url="/api/redoc"  # ReDoc enabled in production
    )

api_router = APIRouter(prefix="/api")

# Add CORS middleware

origins = ["http://localhost", "http://localhost:8080", "http://localhost:8081"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#############################################
# FastAPI Endpoints
#############################################

@api_router.get("/test")
async def test():
    """
    Test endpoint to verify the API is running.
    """
    logger.info("Test endpoint called")
    return {"message": "API is running successfully!"}


@api_router.post("/stream_query")
async def stream_endpoint(
    request: MessageRequest,
    auth_result: dict = Security(auth.verify)
):
    """
    Main streaming chat endpoint with AI-powered responses for parachuting theory training.

    This endpoint uses **Server-Sent Events (SSE)** to stream responses in real-time as the AI
    agent processes the query. The agent can execute tools (like quiz retrieval) and provide
    contextual educational support.

    ## Authentication

    **Required**: Bearer JWT token from Auth0

    ```http
    Authorization: Bearer <your_jwt_token>
    ```

    ## Request Format

    **Content-Type**: `application/json`

    **Body**:
    - `message` (string, required): User query text
    - `userid` (string, required): User identifier (min length: 1)

    **Example**:
    ```json
    {
      "message": "Give me a theory question about meteorology",
      "userid": "google-oauth2|104612087445133776110"
    }
    ```

    ## Response Format (SSE Stream)

    **Media Type**: `text/event-stream`

    The stream produces JSON events with different types. Each event is prefixed with `data:` per SSE specification.

    ### Event Type 1: `agent_message`

    Incremental text chunks from the AI response. Clients should concatenate these to build the complete message.

    ```json
    data: {"type": "agent_message", "data": "Ecco"}
    data: {"type": "agent_message", "data": " una"}
    data: {"type": "agent_message", "data": " domanda..."}
    ```

    ### Event Type 2: `tool_result`

    Result from tool execution. Currently, the main tool is **domanda_teoria** for quiz questions.

    ```json
    data: {
      "type": "tool_result",
      "tool_name": "domanda_teoria",
      "data": {
        "capitolo": 1,
        "capitolo_nome": "Meteorologia applicata al paracadutismo",
        "numero": 3,
        "testo": "A quale quota si formano i cumuli?",
        "opzioni": [
          {"id": "A", "testo": "1000-2000 metri"},
          {"id": "B", "testo": "2000-4000 metri"},
          {"id": "C", "testo": "4000-6000 metri"}
        ],
        "risposta_corretta": "A"
      },
      "final": true
    }
    ```

    ## Available Tools

    ### domanda_teoria - Quiz Question Retrieval

    The AI agent can retrieve parachuting theory exam questions in 4 different modes:

    1. **Random Question** (Exam Simulation)
       - Trigger: "Give me a theory question", "Simulate an exam"
       - Returns: Random question from entire database (all 10 chapters)

    2. **Random Question by Chapter**
       - Trigger: "Question from chapter 3", "Ask me about meteorology (chapter 1)"
       - Returns: Random question from specified chapter (1-10)

    3. **Specific Question**
       - Trigger: "Question 5 from chapter 2", "Show me chapter 3, question 10"
       - Returns: Exact question by chapter and number

    4. **Text Search**
       - Trigger: "Question about VNE", "Question about opening altitude"
       - Returns: Question matching search keywords

    **Available Chapters** (1-10):
    1. Meteorologia applicata al paracadutismo
    2. Aerodinamica applicata al corpo in caduta libera
    3. Tecnologia degli equipaggiamenti e strumenti in uso
    4. Tecnica di direzione di lancio
    5. Tecnica di utilizzo dei paracadute plananti
    6. Elementi e procedure generali di sicurezza
    7. Elementi e procedure di sicurezza nel lavoro relativo in caduta libera
    8. Elementi e procedure di sicurezza nel volo in formazione con paracadute planante
    9. Procedure in situazioni di emergenza
    10. Normativa aeronautica attinente il paracadutismo

    ## Response Status Codes

    - **200**: Stream started successfully
    - **401/403**: Invalid or missing authentication token
    - **422**: Invalid request payload (missing userid or empty message)
    - **500**: Internal server error

    ## Client Implementation Example

    ### JavaScript (EventSource)

    ```javascript
    const eventSource = new EventSource('/api/stream_query', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });

    let fullResponse = "";

    eventSource.onmessage = (event) => {
      const parsed = JSON.parse(event.data);

      switch(parsed.type) {
        case 'agent_message':
          fullResponse += parsed.data;
          displayText(fullResponse);
          break;

        case 'tool_result':
          if (parsed.tool_name === 'domanda_teoria') {
            displayQuizQuestion(parsed.data);
          }
          break;
      }
    };

    eventSource.onerror = (error) => {
      console.error('Stream error:', error);
      eventSource.close();
    };
    ```

    ### Python (requests with stream)

    ```python
    import requests
    import json

    response = requests.post(
        'https://air-coach.com/api/stream_query',
        headers={'Authorization': f'Bearer {token}'},
        json={'message': 'Give me a question', 'userid': 'user123'},
        stream=True,
        timeout=30
    )

    for line in response.iter_lines():
        if line:
            data = line.decode('utf-8').removeprefix('data: ')
            event = json.loads(data)

            if event['type'] == 'agent_message':
                print(event['data'], end='', flush=True)
            elif event['type'] == 'tool_result':
                print(f"\\nQuiz: {event['data']}")
    ```

    ## Best Practices

    - **Timeout**: Set client timeout to **30 seconds** (serverless function limit)
    - **Retry Logic**: Implement exponential backoff for connection failures
    - **Event Concatenation**: Always concatenate `agent_message` chunks for full response
    - **Error Handling**: Check HTTP status before processing stream
    - **Connection Management**: Close EventSource when done to free resources

    ## Features

    - **Persistent Memory**: Conversation history maintained across sessions
    - **User Personalization**: Responses adapted based on Auth0 user profile
    - **Context-Aware**: AI agent has access to up-to-date educational content from S3
    - **Streaming**: Real-time response generation for better UX
    """
    try:
        token = auth_result.get('access_token') or auth_result.get('token')
        logger.info(f"Request received: \ntoken_len= {len(token)}\nmessage= {request.message}\nuserid= {request.userid}")
        stream_response = ask(request.message, request.userid, chat_history=True, stream=True, user_data=True)
        logger.info("Starting streaming response...")
        return StreamingResponse(stream_response, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Exception occurred in /stream_query: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@api_router.post("/update_docs")
async def update_docs_endpoint():
    """
    Endpoint that triggers a manual refresh of the document cache and rebuilds the system prompt.
    Returns information about the updated documents including:
    - A success message
    - The total number of documents
    - Details for each document (title and last modified date)
    """
    try:
        update_result = update_docs()
        system_prompt = update_result["system_prompt"]
        
        try:
            file = create_prompt_file(system_prompt)
        except Exception as file_error:
            logger.error(f"Error creating prompt file: {str(file_error)}")
            raise HTTPException(status_code=500, detail="Error creating prompt file")
        
        return {
            "message": update_result["message"],
            "docs_count": update_result["docs_count"],
            "docs_details": update_result["docs_details"],
            "prompt_file": file,
            "system_prompt": system_prompt
        }
    except Exception as e:
        logger.error(f"Exception occurred while updating docs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(api_router) # for /api/ prefix


from fastapi import FastAPI, HTTPException, APIRouter, Security, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
logger = logging.getLogger("uvicorn")
from src.models import MessageRequest
from src.rag import ask
from src.update_docs import update_docs
from src.s3_utils import create_prompt_file
from src.auth import VerifyToken
from src.env import MONITORING_API_KEY

auth = VerifyToken()

app = FastAPI(
    title='AIR Coach API',
    version='0.4',
    description='''
# AIR Coach API

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
    Main streaming chat endpoint 
    
    This endpoint uses **Server-Sent Events (SSE)** 
    The agent can execute tools (like quiz retrieval)

    ## Authentication

    **Required**: Bearer JWT token 

    ## Request Format

    **Content-Type**: `application/json`

    **Body**:
    - `message` (string, required): User query text
    - `userid` (string, required): User identifier (min length: 1)

    **Example**:
    ```json
    {
      "message": "Ciao, puoi farmi una domanda di teoria?",
      "userid": "[userid_string]"
    }
    ```

    ## Response Format (SSE Stream)

    **Media Type**: `text/event-stream`

    The stream produces JSON events with different types. Each event is prefixed with `data:` per SSE specification.

    ### Event Type 1: `agent_message`

    Incremental text chunks from the AI response. Clients should concatenate these to build the complete message.

    ```json
    data: {"type": "agent_message", "data": "Ecco", "message_id": "userid_2026-01-19T14:26:03.779"}
    data: {"type": "agent_message", "data": " una", "message_id": "userid_2026-01-19T14:26:03.779"}
    data: {"type": "agent_message", "data": " domanda...", "message_id": "userid_2026-01-19T14:26:03.779"}
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
      "final": true,
      "message_id": "userid_2026-01-19T14:26:03.779"
    }
    ```

    ## Response Status Codes

    - **200**: Stream started successfully
    - **401/403**: Invalid or missing authentication token
    - **422**: Invalid request payload (missing userid or empty message)
    - **500**: Internal server error
    """
    try:
        token = auth_result.get('access_token') or auth_result.get('token')
        logger.info(f"Request received: \ntoken_len= {len(token)}\nmessage= {request.message}\nuserid= {request.userid}")
        stream_response = ask(request.message, request.userid, chat_history=True, user_data=True, token=token)
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

@api_router.get("/monitoring")
async def monitoring_endpoint(
    request: Request,
    hours: int = Query(default=24, ge=1, le=720),
):
    """
    Monitoring dashboard endpoint.

    Returns aggregated metrics: token usage, cache analysis, cost projections,
    rate limit events, and recommendations.

    Protected by static API key via X-Monitoring-Key header.
    If MONITORING_API_KEY is not set, the endpoint returns 403.

    Query params:
        hours: Number of hours to look back (default: 24, max: 720)
    """
    # Verify API key
    if not MONITORING_API_KEY:
        raise HTTPException(status_code=403, detail="Monitoring endpoint not configured")

    api_key = request.headers.get("X-Monitoring-Key", "")
    if api_key != MONITORING_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid monitoring API key")

    try:
        from src.monitoring.dashboard import get_monitoring_report
        report = get_monitoring_report(hours=hours)
        return report
    except Exception as e:
        logger.error(f"Error generating monitoring report: {e}")
        raise HTTPException(status_code=500, detail="Error generating monitoring report")

app.include_router(api_router) # for /api/ prefix


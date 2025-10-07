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
    description='API for AIR Coach agent<br />- with Gemini 2.5<br />- with tools',
    #docs_url=None if is_production else "/api/docs",  # Disabilita /docs in produzione
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


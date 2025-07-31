from fastapi import FastAPI, HTTPException, APIRouter, Security
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models import MessageRequest
from app.rag import ask, update_docs
from app.s3_utils import create_prompt_file
import uvicorn
from app.auth import VerifyToken
import logging
from app.services.agent_manager import AgentManager
import uuid
from app.config import settings

from fastapi import FastAPI, Security
from app.auth import VerifyToken

logger = logging.getLogger("uvicorn")

auth = VerifyToken()

app = FastAPI(
    title='Air-coach api', 
    version='0.2', 
    description='API for AIR Coach application<br />now with Gemini 2.0',
    docs_url=None if settings.is_production else "/api/docs",  # Disabilita /docs in produzione
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

@app.on_event("startup")
async def startup_event():    
    try:
        AgentManager.load_agents_from_db()
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

@api_router.get("/test")
async def test():
    """
    Test endpoint to verify the API is running.
    """
    logger.info("Test endpoint called")
    return {"message": "API is running successfully!"}


#############################################
# FastAPI Endpoints
#############################################

@api_router.post("/stream_agent")
async def stream_endpoint(
    request: MessageRequest
):
    try:
        # Ensure thread_id is not None
        thread_id = str(uuid.uuid4())
        logger.info(f"Request received: \ntoken= \nmessage= {request.message}\nuserid= {request.userid}\nthread_id= {thread_id}")
        # Process the chat request through the agent manager
        result = await AgentManager.process_chat(
            query = request.message,
            agent_id = "air-coach",
            thread_id=thread_id,
            include_history=True,
            user_id=request.userid
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.info(f"Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing chat")

@api_router.post("/stream_query")
async def stream_endpoint(
    request: MessageRequest,
    auth_result: dict = Security(auth.verify)
):
    try:
        token = auth_result.get('access_token') or auth_result.get('token')
        logger.info(f"Request received: \ntoken= {token}\nmessage= {request.message}\nuserid= {request.userid}")
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
    import json
    try:
        update_result = update_docs()
        system_prompt = json.loads(json.dumps(update_result["system_prompt"]).replace('\n', '\\n'))
        
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

if __name__ == "__main__":
    uvicorn.run(app, port=8080, log_level="info")

from fastapi import FastAPI, HTTPException, APIRouter, Security
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.logging_config import logger
from src.models import MessageRequest
from src.rag import ask, update_docs
from src.s3_utils import create_prompt_file
from src.env import is_production
import uvicorn
from src.auth import VerifyToken

auth = VerifyToken()

from fastapi import FastAPI, Security
from src.auth import VerifyToken

auth = VerifyToken()

app = FastAPI(
    title='Air-coach api', 
    version='0.2', 
    description='API for AIR Coach application<br />now with Gemini 2.0',
    docs_url=None if is_production else "/api/docs",  # Disabilita /docs in produzione
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

@api_router.post("/stream_query")
async def stream_endpoint(
    request: MessageRequest,
    auth_result: dict = Security(auth.verify)
):
    try:
        token = auth_result.get('access_token') or auth_result.get('token')
        logger.info(f"Token received from frontend: {token}")
        stream_response = ask(request.message, request.userid, chat_history=True, stream=True, user_data=True)
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

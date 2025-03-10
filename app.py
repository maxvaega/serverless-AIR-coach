from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.logging_config import logger
from src.models import MessageRequest, MessageResponse
from src.rag import ask, update_docs
from src.auth0 import get_user_metadata
from src.utils import format_user_metadata, validate_user_id
from src.cache import set_cached_user_data
from src.env import is_production
import uvicorn

app = FastAPI(
    title='Air-coach api', 
    version='0.2', 
    description='API for AIR Coach application<br />now with Gemini 2.0',
    docs_url=None if is_production else "/api/docs",  # Disabilita /docs in produzione
    )

api_router = APIRouter(prefix="/api")

# Add CORS middleware

origins = ["http://localhost", "http://localhost:8080"]

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
async def stream_endpoint(request: MessageRequest):
    if not validate_user_id(request.userid):
        logger.error("Unauthorized")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        stream_response = ask(request.message, request.userid, chat_history=True, stream=True, user_data=True)
        return StreamingResponse(stream_response, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
        return {
            "message": update_result["message"],
            "docs_count": update_result["docs_count"],
            "docs_details": update_result["docs_details"]
        }
    except Exception as e:
        logger.error(f"Exception occurred while updating docs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@api_router.post("/user_query")
async def user_query_endpoint(user_id: str):
    """
    Endpoint that retrieves and formats user metadata from Auth0.

    :param user_id: L'ID dell'utente.
    :return: Dati utente grezzi e stringa formattata.
    """
    try:
        # Recupera i metadata dall'API di Auth0
        user_metadata = get_user_metadata(user_id)
        if not user_metadata:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Formatta i metadata
        formatted_data = format_user_metadata(user_metadata)
        
        # Salva nella cache, sovrascrivendo eventuali dati esistenti
        set_cached_user_data(user_id, formatted_data)
        
        return {
            "user_metadata": user_metadata,
            "formatted_data": formatted_data
        }
    except Exception as e:
        logger.error(f"Errore nell'elaborazione della richiesta user_query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint rimossi

# @api_router.get("/")
# def read_root():
#     return {"message": "Welcome to the AIR Coach /API"}

# @api_router.post("/query")
# async def query_endpoint(request: MessageRequest):
#     """
#     Endpoint to handle query requests.

#     This endpoint receives a POST request with a message query, processes the query,
#     and returns a response.

#     Args:
#         request (MessageRequest): The request object containing the query message, user ID, and session ID.

#     Returns:
#         MessageResponse: The response object containing the original query, the result of the query,
#         the user ID, and the session ID.

#     Raises:
#         HTTPException: If an exception occurs during processing, a 500 Internal Server Error is raised.

#     Logs:
#         Logs the start of the request, the request details, the processing status, the response, 
#         and any exceptions that occur.
#     """
#     logger.info("Start Request")
#     logger.info(f"Request: {request}")
#     try:
#         logger.info("Processing Request")

#         response_message = ask(request.message, request.userid, stream=False) #, chat_history=chat_history)
#         logger.info(f"Response: {response_message.content}")

#         # Create the response using the MessageResponse model
#         message_response = MessageResponse(
#             query=request.message,
#             result=response_message.content,
#             userid=request.userid
#         )
        
#         return message_response

#     except Exception as e:
#         logger.error(f"Exception occurred: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))
    
# @api_router.post("/test/", response_model=MessageResponse)
# async def test_endpoint(request: MessageRequest):
#     try:
#         # Check if message is empty or contains only whitespace
#         if not request.message or request.message.isspace():
#             print("Received cannot be empty")
#             raise HTTPException(status_code=400, detail="message cannot be empty")

#         # Create response message
#         response_message = f"Received: {request.message}"
#         print(response_message)

#         # Create the response using the MessageResponse model
#         message_response = MessageResponse(
#             query=request.message,
#             result=response_message,
#             userid=request.userid
#         )

#         # Return response
#         return message_response

#     except Exception as e:
#         # Handle unexpected errors
#         print(str(e))
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


app.include_router(api_router) # for /api/ prefix

if __name__ == "__main__":
    uvicorn.run(app, port=8080, log_level="info")

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.logging_config import logger
from src.models import MessageRequest, MessageResponse
from src.rag import ask
import uvicorn
import os

# Load environment variables

DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

app = FastAPI(title='aistruttore-api-gemini', version='0.1', description='API for AIstruttore chatbot<br />Gemini edition')

# Add CORS middleware

origins = ["http://localhost", "http://localhost:8080", "*"]

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

@app.get("/")
def read_root():
    return {"message": "Welcome to the AIstruttore API"}


@app.post("/query")
async def query_endpoint(request: MessageRequest):
    """
    Endpoint to handle query requests.

    This endpoint receives a POST request with a message query, processes the query,
    and returns a response.

    Args:
        request (MessageRequest): The request object containing the query message, user ID, and session ID.

    Returns:
        MessageResponse: The response object containing the original query, the result of the query,
        the user ID, and the session ID.

    Raises:
        HTTPException: If an exception occurs during processing, a 500 Internal Server Error is raised.

    Logs:
        Logs the start of the request, the request details, the processing status, the response, 
        and any exceptions that occur.
    """
    logger.info("Start Request")
    logger.info(f"Request: {request}")
    try:
        logger.info("Processing Request")

        response_message = ask(request.message, request.userid, stream=False) #, chat_history=chat_history)
        logger.info(f"Response: {response_message.content}")

        # Create the response using the MessageResponse model
        message_response = MessageResponse(
            query=request.message,
            result=response_message.content,
            userid=request.userid
        )
        
        return message_response

    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stream_query")
async def stream_endpoint(request: MessageRequest):
    try:
        stream_response = ask(request.message, request.userid, stream=True)
        return StreamingResponse(stream_response, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/", response_model=MessageResponse)
async def test_endpoint(request: MessageRequest):
    try:
        # Check if message is empty or contains only whitespace
        if not request.message or request.message.isspace():
            print("Received cannot be empty")
            raise HTTPException(status_code=400, detail="message cannot be empty")

        # Create response message
        response_message = f"Received: {request.message}"
        print(response_message)

        # Create the response using the MessageResponse model
        message_response = MessageResponse(
            query=request.message,
            result=response_message,
            userid=request.userid
        )

        # Return response
        return message_response

    except Exception as e:
        # Handle unexpected errors
        print(str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, port=8080, log_level="info")

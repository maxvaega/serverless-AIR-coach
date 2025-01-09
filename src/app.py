from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from pydantic import BaseModel
from query import ask
#from database import insert_data, get_data
import uvicorn
from typing import Optional
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

app = FastAPI()

# Add CORS middleware
origins = ["http://localhost", "http://localhost:8080", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request model
class MessageRequest(BaseModel):
    message: str
    userid: Optional[str] = None
    sessionId: Optional[str] = None


# Define response model
class MessageResponse(BaseModel):
    query: str
    result: str
    userid: Optional[str] = None
    sessionId: Optional[str] = None


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
        
        # Check Chat History
        # chat_history = []
        # try:
        #     data = get_data(DATABASE_NAME, COLLECTION_NAME, {"userid": request.userid, "sessionId": request.sessionId})
        #     for item in data:
        #         chat_history.append(("human", item["human"]))
        #         chat_history.append(("system", item["system"]))
        # except Exception as e:
        #     logger.error(f"Error getting chat history: {str(e)}")

        response_message = ask(request.message) #, chat_history=chat_history)
        logger.info(f"Response: {response_message}")

        # Create the response using the MessageResponse model
        message_response = MessageResponse(
            query=request.message,
            result=response_message.get("answer", "No answer available"),
            userid=request.userid,
            sessionId=request.sessionId
        )
        
        # insert_data(DATABASE_NAME, COLLECTION_NAME, {
        #     "human": message_response.query,
        #     "system": message_response.result,
        #     "userid": message_response.userid,
        #     "sessionId": message_response.sessionId
        # })
        
        return message_response

    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stream_query")
async def stream_endpoint(request: MessageRequest):
    try:
        stream_response = ask(request.message, stream=True)
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
            userid=request.userid,
            sessionId=request.sessionId
        )

        # Return response
        return message_response

    except Exception as e:
        # Handle unexpected errors
        print(str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, port=8080)

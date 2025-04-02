# AIR Coach API - v2.0

AIR Coach API is a FastAPI-based application designed for handling chatbot interactions.

## Features

- **Query Endpoint**: Handle query requests and return responses.
- **Streaming Query Endpoint**: Stream responses for long-running queries.
- **Docs update Endpoint**: refreshes the docs in cache to updated the LLM context
- **Test Endpoint**: Test the API with a simple request-response mechanism.
- **CORS Middleware**: Allow cross-origin requests.
- **LLM Model**: Gemini 2.0 Flash
- **AWS S3 Context load**: dinamically loads context from .md files hosted in AWS S3
- **User information**: reads data from auth0 to add to the LLM context window
- **conversation history**: stores and retrieves conversation history in DynamoDB

## Requirements

- Python 3.7+
- FastAPI
- Uvicorn
- Pydantic
- dotenv
- boto3

## Environment Variables

see the file **.env.example** for the environment variables

# Local Test

## FastAPI

```sh
python app.py

# Example output
INFO:     Started server process [67877]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)

```

## Test Single Query

```sh
python -m src.test

# Example Output
Enter the query: 

```

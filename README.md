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

## Requirements

- Python 3.7+
- FastAPI
- Uvicorn
- Pydantic
- MongoDB
- dotenv

## Environment Variables

The following environment variables are required to configure the application:

```
# Google AI Configuration
GOOGLE_API_KEY=<GOOGLE_API_KEY>

# Langsmith Configuration
LANGCHAIN_TRACING_V2=<LANGCHAIN_TRACING_V2>
LANGCHAIN_ENDPOINT=<LANGCHAIN_ENDPOINT>
LANGCHAIN_API_KEY=<LANGCHAIN_API_KEY>
LANGCHAIN_PROJECT=<LANGCHAIN_PROJECT>

# MongoDB Configuration
MONGODB_URI=<MONGODB_URI>
DATABASE_NAME=<DATABASE_NAME>
COLLECTION_NAME=<COLLECTION_NAME>

# AWS S3 configuration
AWS_ACCESS_KEY_ID=AWS_ID
AWS_SECRET_ACCESS_KEY=AWS_Secret
BUCKET_NAME="bucket-name"

# Auth0 configuration
AUTH0_DOMAIN=AUTH0_DOMAIN
AUTH0_API_TOKEN=AUTH0_API_TOKEN
```

# Local Test

## FastAPI

```sh
python app.py

# Example output
2025-02-07 11:32:43,980 [INFO] Connected to MongoDB successfully.
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

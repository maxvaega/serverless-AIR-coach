# Air Coach API

Air Coach API is a FastAPI-based application designed for handling chatbot interactions.

## Features

- **Query Endpoint**: Handle query requests and return responses. <www.air-coach.com/api>
- **Streaming Query Endpoint**: Stream responses for long-running queries.
- **Test Endpoint**: Test the API with a simple request-response mechanism.
- **CORS Middleware**: Allow cross-origin requests.

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
# Pinecone Configuration
PINECONE_API_KEY=<PINECONE_API_KEY>
PINECONE_ENVIRONMENT=<PINECONE_ENVIRONMENT>
PINECONE_INDEX_NAME=<PINECONE_INDEX_NAME>
PINECONE_NAMESPACE=<PINECONE_NAMESPACE>

# OpenAI Configuration
OPENAI_API_KEY=<OPENAI_API_KEY>

# Langsmith Configuration
LANGCHAIN_TRACING_V2=<LANGCHAIN_TRACING_V2>
LANGCHAIN_ENDPOINT=<LANGCHAIN_ENDPOINT>
LANGCHAIN_API_KEY=<LANGCHAIN_API_KEY>
LANGCHAIN_PROJECT=<LANGCHAIN_PROJECT>

# MongoDB Configuration
MONGODB_URI=<MONGODB_URI>
DATABASE_NAME=<DATABASE_NAME>
COLLECTION_NAME=<COLLECTION_NAME>
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

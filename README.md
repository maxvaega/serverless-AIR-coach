# AIR Coach API - v2.0

AIR Coach API is a FastAPI-based application designed for handling chatbot interactions.

## Features

- **Streaming Query Endpoint**: Handle query requests and stream responses
- **Docs update Endpoint**: refreshes the docs in cache to updated the LLM context
- **AWS S3 Context load**: dinamically loads context from .md files hosted in AWS S3
- **User information**: reads data from auth0 to add to the LLM context window
- **LLM Model**: Gemini 2.5 Flash

## Requirements

- Python 3.7+
- FastAPI
- Langchain
- MongoDB
- others

## Environment Variables

To set environment variables, copy the file [.env.example](.env.example) and replace the keys

# Local Test

## FastAPI

```sh
uvicorn app:app --reload

# Example output
2025-02-07 11:32:43,980 [INFO] Connected to MongoDB successfully.
INFO:     Started server process [67877]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     Started reloader process [31094] using StatReload

```

## Test Single Query

```sh
python -m src.test

# Example Output
Enter the query: 

```

## To run automatic testing

see [docs/test.md](docs/test.md) for setup and usage with pytest.

# AIR Coach API - v2.2

AIR Coach API is a FastAPI-based application designed for handling chatbot interactions with AI agents powered by LangGraph.

## Features

- **Streaming Query Endpoint**: Handle query requests and stream responses
- **Docs update Endpoint**: refreshes the docs in cache to updated the LLM context
- **AWS S3 Context load**: dinamically loads context from .md files hosted in AWS S3
- **User information**: reads data from Auth0 and adds it to the system prompt (not as chat messages)
- **LLM Model**: Gemini 2.5 Flash
- **LangGraph Integration**: AI agents with custom tools for quiz management
- **Quiz Management Tool**: `domanda_teoria` tool for retrieving and searching quiz questions
 - **Rolling conversation window (pre_model_hook)**: the LLM only receives the last `HISTORY_LIMIT` turns; graph state `messages` is never trimmed

## Requirements

- Python 3.7+
- FastAPI
- Langchain
- LangGraph
- MongoDB
- others

## Environment Variables

To set environment variables, copy the file [.env.example](.env.example) and replace the keys

# Local Test

## FastAPI

#uvicorn run:app --reload
```sh
python run.py

# Example output
2025-02-07 11:32:43,980 [INFO] Connected to MongoDB successfully.
INFO:     Started server process [67877]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     Started reloader process [31094] using StatReload

```

## To run automatic testing

see [tests/readme.md](tests/readme.md) for setup and usage with pytest.

## LangGraph Agent Notes

- The agent is created per-request with `create_react_agent(model, tools, prompt=personalized_prompt, pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT), checkpointer=InMemorySaver())`.
- `personalized_prompt` concatenates user metadata into the system prompt each request; no `AIMessage` is added for user data.
- `thread_id` is versioned per user and prompt version: `f"{userid}:v{prompt_version}"`.
- No trimming on warm path. The rolling window is applied via `pre_model_hook` by setting `llm_input_messages`.

## Changelog

- 2025/08: new tool domanda_teoria to output a json with questions from the db
- 2025/09: rolling window via pre_model_hook, prompt personalization in system prompt, versioned thread_id, no trimming of graph state in warm path
- 2025/09: refactoring file names, logging and env variables. run.py as an entrypoint and fastapi logic as an src.main.
- 2025/09: moved inference to europe-west8 (Milan) + caching in Gemini
- 
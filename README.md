# AIR Coach API - v2.2

AIR Coach API is a FastAPI-based application designed for handling chatbot interactions with AI agents powered by LangGraph.

## Features

- **Streaming Query Endpoint**: Handle query requests and stream responses
- **Docs update Endpoint**: refreshes the docs in cache to updated the LLM context
- **AWS S3 Context load**: dinamically loads context from .md files hosted in AWS S3
- **User information**: reads data from Auth0 and adds it to the system prompt (not as chat messages)
- **LLM Model**: Gemini 3 Flash
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

## Documentation

- **[Functional Analysis](docs/FUNCTIONAL.md)**: Business and product perspective - features, use cases, and end-user flows
- **[Technical Analysis](docs/TECNICAL.md)**: Engineering perspective - architecture, patterns, and implementation details
- **[Testing Documentation](tests/README.md)**: Complete testing strategy, setup and usage with pytest

## Monitoring (Phase 0)

The project includes a monitoring toolkit for tracking token usage, cache effectiveness, costs, and rate limits.

### Token Counter

The `scripts/count_tokens.py` script counts real tokens in the knowledge base documents using the Google Generative AI SDK, and produces per-document breakdowns with cost estimates.

```bash
# Count tokens from local docs
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/

# Count tokens from S3 (production)
python scripts/count_tokens.py

# Include cache probe to verify implicit caching
python scripts/count_tokens.py --local ../Knowledge-AIR-Coach/docs/ --probe-cache
```

Full documentation: [scripts/COUNT_TOKENS.md](scripts/COUNT_TOKENS.md)

### Runtime Token Logging

Every request automatically logs token usage (input, output, cached) to the MongoDB `token_metrics` collection. Controlled by the `ENABLE_TOKEN_LOGGING` env var (default: `true`). Rate limit events (HTTP 429) are captured in `rate_limit_events`.

### Monitoring Endpoint

`GET /api/monitoring?days=30` returns an aggregated report with token usage, cache analysis, cost projections, rate limit events, and recommendations. Protected by Auth0 JWT authentication (same as `/api/stream_query`).

```bash
curl -H "Authorization: Bearer <jwt-token>" https://app.vercel.app/api/monitoring?days=7
```

### CLI Reports

```bash
# Cost report from MongoDB
python scripts/calculate_costs.py --hours 168

# Full monitoring report
python scripts/monitoring_report.py --hours 24
python scripts/monitoring_report.py --hours 24 --json
```

## API Health Check Monitor

The `monitor_api.py` script provides continuous monitoring of the API health endpoint in the production url. It performs automated health checks every 30 seconds, displaying success/failure status with timestamps and detailed error reporting. Run with `python monitor_api.py` to monitor API availability in real-time.

## LangGraph Agent Notes

- The agent is created per-request with `create_react_agent(model, tools, prompt=personalized_prompt, pre_model_hook=build_llm_input_window_hook(HISTORY_LIMIT), checkpointer=InMemorySaver())`.
- `personalized_prompt` concatenates user metadata into the system prompt each request; no `AIMessage` is added for user data.
- `thread_id` is versioned per user and prompt version: `f"{userid}:v{prompt_version}"`.
- No trimming on warm path. The rolling window is applied via pre_model_hook which returns `llm_input_messages`.

## Changelog

- 2025/08: new tool domanda_teoria to output a json with questions from the db
- 2025/09: rolling window via pre_model_hook, prompt personalization in system prompt, versioned thread_id, no trimming of graph state in warm path
- 2025/09: refactoring file names, logging and env variables. run.py as an entrypoint and fastapi logic as an src.main.
- 2025/09: moved inference to europe-west8 (Milan) + caching in Gemini

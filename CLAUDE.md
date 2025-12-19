# AIR Coach API - Claude Code Instructions

## Tech Stack
- **Framework**: FastAPI + LangGraph agents
- **Language**: Python 3.7+
- **LLM**: Google Gemini 3 Flash preview (europe-west8)
- **Database**: MongoDB Atlas
- **Storage**: AWS S3
- **Auth**: Auth0 JWT
- **Deployment**: Vercel Serverless

## Commands (ESSENTIAL ONLY)
- `source /Users/massimoolivieri/Developer/serverless-AIR-coach/.venv/bin/activate`: to activate the python virtual env with all dependencies
- `python run.py`: Start development server
- `pytest -v -rs tests/`: Run all tests
- `pytest -v -rs tests/test_stream_query.py`: E2E streaming tests

## Code Style (CRITICAL RULES)
- **NEVER work on main branch**: Always create a new branch
- **Always run tests**: Execute pytest after any code changes
- **Update documentation**: Modify docs when changing code behavior
- **LangGraph patterns**: Use factory pattern for agents, singleton for checkpointer

## Architecture Patterns
- **Entry point**: `run.py` (Vercel) + `src/main.py` (FastAPI app)
- **Core files**: `src/rag.py` (orchestrator), `src/tools.py` (quiz tool)
- **Agent creation**: Per-request via `AgentManager.create_agent()`
- **Memory**: InMemorySaver (hot) + MongoDB (cold), rolling window via pre_model_hook
- **Threading**: `f"{userid}:v{prompt_version}"` for conversation isolation

## Repository Workflow
- **Branch naming**: `feature/description` from develop branch
- **Commit style**: Descriptive commits with scope
- **PR requirements**: Tests passing, documentation updated
- **Code changes**: Always consult `/docs/Analisi funzionale.md` and `/docs/Analisi tecnica.md`
- **CI/CD**: 3 GitHub workflows - automated testing (test.yml), Claude integration (@claude mentions), PR reviews (claude-code-review.yml)

## Documentation
- **IMPORTANT:** check documentation when you need it, skip the files that are not necessary
- **[Functional Analysis](docs/FUNCTIONAL.md)**: Business and product perspective - features, use cases, and end-user flows
- **[Technical Analysis](docs/TECNICAL.md)**: Engineering perspective - architecture, patterns, and implementation details
- **[Testing Documentation](tests/README.md)**: Complete testing strategy, setup and usage with pytest

## IMPORTANT Notes
- **Serverless constraints**: Agent instances per-request, checkpointer singleton
- **Memory isolation**: Thread ID versioning prevents cross-contamination
- **Testing order**: Unit tests first, then E2E with running server
- **LangGraph tools**: Use MCP servers (Langchain, context7) for library documentation
- **Authentication**: Auth0 JWT required for `/api/stream_query` endpoint
- **Tool output**: `domanda_teoria` returns JSON (not string) for quiz questions
- **Event loop**: Factory pattern prevents "Event loop is closed" in serverless
- **Documentation location**: Technical docs in `/docs/`

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
- IMPORTANTE: Always Activate python virtual env with all dependencies (folder .venv)
- `python run.py`: Start development server (only needed for E2E tests)

### Testing Commands (Three-Tier Strategy)
- `pytest -m unit -v`: Run unit tests (fast, mocked, < 10 seconds) - **DEFAULT**
- `pytest -m integration -v`: Run integration tests (TestClient, no server needed, 30-60 seconds)
- `pytest -v`: Run unit + integration tests (default, skips E2E)
- `pytest -m e2e -v`: Run E2E tests (requires manual server: python run.py)
- `pytest --cov=src -v`: Run tests with coverage report

### Common Testing Workflows
- **Development**: `pytest -m unit -v` (fast feedback loop)
- **Pre-commit**: `pytest -v` (unit + integration, no manual server)
- **Pre-deployment**: `pytest -m e2e -v` (full validation, requires server)

## Code Style (CRITICAL RULES)
- **NEVER work on main branch**: Always create a new branch
- **Always run tests**: Execute pytest after any code changes
- **Update documentation**: Modify docs when changing code behavior
- **LangGraph patterns**: Use factory pattern for agents, singleton for checkpointer
- **get documentation when using third party libraries**: use context7 or web search whenever working with third party libraries

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
- **CI/CD**: 3 GitHub workflows - automated testing (test.yml), Claude integration (@claude mentions), PR reviews (claude-code-review.yml)

## Documentation
- **[Testing Documentation](tests/README.md)**: Complete testing strategy, setup and usage with pytest

## IMPORTANT Notes
- **Serverless constraints**: Agent instances per-request, checkpointer singleton
- **Memory isolation**: Thread ID versioning prevents cross-contamination
- **Testing strategy**: Three-tier approach (unit → integration → e2e)
  - Unit tests: Fast, mocked dependencies, run on every change
  - Integration tests: TestClient-based, NO manual server needed (NEW)
  - E2E tests: Manual server required, pre-deployment only
- **LangGraph tools**: Use MCP servers (Langchain, context7) or web serach for library documentation
- **Authentication**: Auth0 JWT required for `/api/stream_query` endpoint
- **Tool output**: `domanda_teoria` returns JSON (not string) for quiz questions
- **Event loop**: Factory pattern prevents "Event loop is closed" in serverless
- **Test markers**: Use @pytest.mark.unit, @pytest.mark.integration, or @pytest.mark.e2e

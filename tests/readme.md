# Testing Documentation - AIR Coach API

## Test Strategy Overview

AIR Coach API uses a **three-tier testing strategy** following FastAPI best practices:

1. **Unit Tests**: Fast, isolated tests with mocked dependencies
2. **Integration Tests**: TestClient-based tests (no manual server required)
3. **E2E Tests**: Full deployment validation (manual server required)

**Key Improvement**: 95% of tests now run without manual server startup, significantly improving developer experience and CI/CD performance.

---

## Test Categories

### 1. Unit Tests (`@pytest.mark.unit`)
- **Speed**: < 10 seconds total
- **Dependencies**: Fully mocked (MongoDB, LLM, S3, Auth0)
- **Purpose**: Test individual components in isolation
- **When to run**: On every code change, before commit

### 2. Integration Tests (`@pytest.mark.integration`)
- **Speed**: 30-60 seconds
- **Dependencies**: FastAPI TestClient (no manual server needed)
- **Purpose**: Test API endpoints and request/response cycles
- **When to run**: On every commit, in CI/CD pipeline

### 3. E2E Tests (`@pytest.mark.e2e`)
- **Speed**: 2-5 minutes
- **Dependencies**: Manual server startup required
- **Purpose**: Deployment validation and smoke testing
- **When to run**: Pre-deployment, manual validation only

---

## Running Tests

### Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run unit tests only (default, fastest)
pytest -m unit -v

# Run integration tests (TestClient, no server needed)
pytest -m integration -v

# Run unit + integration (recommended for development)
pytest -m "unit or integration" -v

# Run ALL tests including E2E (requires manual server)
pytest -v
```

### Test Selection by Marker

```bash
# Unit tests only (fast, mocked dependencies)
pytest -m unit -v -rs

# Integration tests only (TestClient, no manual server)
pytest -m integration -v -rs

# E2E tests only (requires: python run.py)
pytest -m e2e -v -rs

# Skip E2E tests (default behavior via pytest.ini)
pytest -m "not e2e" -v -rs
```

### Running Specific Test Files

```bash
# Unit tests
pytest -v tests/test_tools.py                   # Tool functionality
pytest -v tests/test_history_hook.py            # History management
pytest -v tests/test_history_window.py          # Window management
pytest -v tests/test_prompt_personalization.py  # Prompt building
pytest -v tests/test_caching.py                 # Cache configuration

# Integration tests (NEW - uses TestClient)
pytest -v tests/test_stream_query_testclient.py # Streaming endpoint (no manual server)

# E2E tests (require manual server: python run.py)
pytest -v tests/test_stream_query.py            # Streaming endpoint (manual server)
pytest -v tests/test_update_docs.py             # Document refresh (manual server)
```

### Coverage Reports

```bash
# Unit tests with coverage
pytest -m unit -v --cov=src --cov-report=term-missing

# Integration tests with coverage (append to unit coverage)
pytest -m integration -v --cov=src --cov-append --cov-report=term-missing

# Combined coverage report
pytest -m "unit or integration" -v --cov=src --cov-report=html
open htmlcov/index.html  # View coverage in browser
```

---

## Test Files Structure

```
tests/
├── conftest.py                          # Pytest config + fixtures (markers, TestClient)
├── pytest.ini                           # Pytest settings (at project root)
│
├── Unit Tests (@pytest.mark.unit)
│   ├── test_tools.py                    # domanda_teoria tool (mocked DB)
│   ├── test_history_hook.py             # History management hooks
│   ├── test_history_window.py           # Message window logic
│   ├── test_prompt_personalization.py   # Prompt building
│   └── test_caching.py                  # Cache configuration
│
├── Integration Tests (@pytest.mark.integration)
│   └── test_stream_query_testclient.py  # Streaming endpoint (TestClient)
│
└── E2E Tests (@pytest.mark.e2e)
    ├── test_stream_query.py             # Streaming endpoint (manual server)
    └── test_update_docs.py              # Document refresh (manual server)
```

---

## Detailed Test Descriptions

### Unit Tests (Mocked Dependencies)

#### `test_tools.py`
- **Purpose**: Test `domanda_teoria` tool in isolation
- **Mocking**: Complete MongoDB isolation with mock quiz data
- **Coverage**:
  - Random question selection
  - Chapter-specific questions
  - Exact question retrieval by number
  - Text search functionality
  - Error handling and validation
- **Speed**: < 2 seconds

#### `test_history_hook.py`
- **Purpose**: Test pre_model_hook for conversation memory
- **Mocking**: Message state simulation
- **Coverage**:
  - Rolling window functionality
  - llm_input_messages generation
  - State updates
- **Speed**: < 1 second

#### `test_history_window.py`
- **Purpose**: Test conversation history windowing
- **Coverage**:
  - Message filtering (last N turns)
  - Tool message preservation
  - Turn counting logic
- **Speed**: < 1 second

#### `test_prompt_personalization.py`
- **Purpose**: Test user-specific prompt generation
- **Coverage**:
  - System prompt concatenation
  - User metadata injection
  - Thread ID versioning
- **Speed**: < 1 second

#### `test_caching.py`
- **Purpose**: Test Google Cloud caching configuration
- **Mocking**: LLM configuration objects
- **Coverage**:
  - Cache settings validation
  - Environment variable parsing
- **Speed**: < 1 second

---

### Integration Tests (TestClient, No Manual Server)

#### `test_stream_query_testclient.py` ✨ NEW
- **Purpose**: Test `/api/stream_query` endpoint without manual server
- **Method**: FastAPI TestClient (built-in HTTP testing)
- **Authentication**: Auto-generated Auth0 tokens via fixtures
- **Coverage**:
  - Valid streaming requests (SSE format validation)
  - Invalid token rejection (401/403)
  - Missing token rejection (403)
  - Invalid payload validation (422)
  - Tool execution and MongoDB persistence
  - message_id consistency across chunks
- **Speed**: 30-60 seconds
- **Advantages**:
  - No manual server startup required
  - Faster execution than E2E tests
  - Easier to debug
  - Reliable in CI/CD

**Key Difference from E2E**:
```python
# E2E (old): Requires manual server
with httpx.Client() as client:
    response = client.post("http://localhost:8080/api/stream_query", ...)

# Integration (new): Uses TestClient, no server needed
from fastapi.testclient import TestClient
with test_client.stream("POST", "/api/stream_query", ...) as response:
    ...
```

---

### E2E Tests (Manual Server Required)

#### `test_stream_query.py`
- **Purpose**: Full deployment validation with real server
- **Requirements**: `python run.py` must be running
- **Use case**: Pre-deployment smoke testing only
- **Coverage**: Same as integration tests but validates full deployment stack
- **Speed**: 2-5 minutes
- **When to skip**: Use integration tests instead for development

#### `test_update_docs.py`
- **Purpose**: Test S3 document refresh endpoint
- **Requirements**: `python run.py` + AWS S3 access
- **Coverage**: Document loading, cache refresh, prompt updates
- **Note**: Currently commented out, can be migrated to TestClient

---

## Fixtures (tests/conftest.py)

### Session-Scoped Fixtures

#### `test_client`
```python
@pytest.fixture(scope="session")
def test_client():
    """FastAPI TestClient for integration tests"""
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app)
```

### Function-Scoped Fixtures

#### `auth_headers`
```python
@pytest.fixture
def auth_headers():
    """Generate Auth0 token headers for authenticated requests"""
    # Tries TEST_AUTH_TOKEN env var first, then generates token
    # Skips test if token generation fails
```

#### `test_user_id`
```python
@pytest.fixture
def test_user_id():
    """Standard test user ID for integration tests"""
    return "google-oauth2|104612087445133776110"
```

---

## Authentication for Tests

### Integration Tests (Automatic)
Auth is handled automatically by the `auth_headers` fixture:

```python
@pytest.mark.integration
def test_endpoint(test_client, auth_headers):
    response = test_client.post("/api/stream_query",
                                json=payload,
                                headers=auth_headers)
```

### E2E Tests (Environment Variable)
Set `TEST_AUTH_TOKEN` or use auto-generation:

```bash
export TEST_AUTH_TOKEN="your-jwt-token"
pytest -m e2e -v
```

---

## CI/CD Integration

### GitHub Actions Workflow (`.github/workflows/test.yml`)

**Optimized execution order**:

1. **Unit tests** (fast feedback, < 10 seconds)
   ```yaml
   - name: Run unit tests
     run: pytest -m unit -v -rs --cov=src
   ```

2. **Integration tests** (no server needed, 30-60 seconds)
   ```yaml
   - name: Run integration tests
     run: pytest -m integration -v -rs --cov=src --cov-append
   ```

3. **E2E tests** (manual server, only on workflow_dispatch)
   ```yaml
   - name: Run E2E tests
     if: github.event_name == 'workflow_dispatch'
     run: |
       python run.py &
       sleep 5
       pytest -m e2e -v
   ```

**Benefits**:
- Faster CI/CD feedback (unit + integration < 2 minutes)
- No server startup overhead for 95% of tests
- E2E tests only run when explicitly triggered

---

## Debugging Tests

### Verbose Output
```bash
# Maximum verbosity
pytest -v -s tests/test_name.py

# Show print statements
pytest -s -v tests/test_name.py

# Stop on first failure
pytest -x -v tests/

# Show test markers
pytest --markers
```

### Common Issues

#### Issue: Integration test fails with "Connection refused"
**Solution**: You're using E2E tests by mistake. Use integration tests instead:
```bash
pytest -m integration -v  # Uses TestClient, no server needed
```

#### Issue: E2E test fails with "Connection refused"
**Solution**: Start the server manually:
```bash
# Terminal 1
python run.py

# Terminal 2
pytest -m e2e -v
```

#### Issue: Auth0 token generation fails
**Solution**: Set `TEST_AUTH_TOKEN` environment variable:
```bash
export TEST_AUTH_TOKEN="your-jwt-token"
pytest -m integration -v
```

#### Issue: MongoDB connection errors
**Solution**: Check `.env` file for correct `MONGODB_URI`

---

## Best Practices

### When to Use Each Test Type

| Scenario | Test Type | Command |
|----------|-----------|---------|
| Developing new feature | Unit | `pytest -m unit -v` |
| Testing API endpoint | Integration | `pytest -m integration -v` |
| Before committing code | Unit + Integration | `pytest -m "unit or integration" -v` |
| Before deployment | E2E (manual server) | `pytest -m e2e -v` |
| Quick validation | Unit only | `pytest -m unit -v` |

### Development Workflow

1. **Write unit tests first** for new functionality
2. **Run unit tests** frequently during development
3. **Write integration tests** for API endpoints
4. **Run integration tests** before committing
5. **Run E2E tests** only before deployment (optional)

### Test Coverage Goals

- **Unit tests**: >90% coverage for isolated components
- **Integration tests**: 100% API endpoint coverage
- **E2E tests**: Smoke testing only (critical paths)

---

## Updating Tests

When modifying code:

1. **Update corresponding tests** to maintain synchronization
2. **Add new test cases** for new functionality
3. **Mark tests correctly**:
   - Use `@pytest.mark.unit` for mocked tests
   - Use `@pytest.mark.integration` for TestClient tests
   - Use `@pytest.mark.e2e` for manual server tests
4. **Update documentation** (this file) for test changes
5. **Verify coverage** with `pytest --cov=src`

---

## Migration from E2E to Integration Tests

### Old Approach (E2E with manual server)
```python
# Requires: python run.py
import httpx

def test_endpoint():
    with httpx.Client() as client:
        response = client.post("http://localhost:8080/api/stream_query", ...)
```

### New Approach (Integration with TestClient)
```python
# No server needed
@pytest.mark.integration
def test_endpoint(test_client, auth_headers):
    response = test_client.post("/api/stream_query",
                                json=payload,
                                headers=auth_headers)
```

**Benefits**:
- No manual server startup
- Faster execution
- Better isolation
- Easier debugging

---

## Quick Reference

### Most Common Commands

```bash
# Fast development testing (unit tests only)
pytest -m unit -v

# Full development testing (unit + integration, no server)
pytest -v

# Pre-deployment validation (with manual server)
python run.py  # Terminal 1
pytest -m e2e -v  # Terminal 2

# Coverage report
pytest -m "unit or integration" --cov=src --cov-report=html
```

### Environment Variables

```bash
# Optional: Set test auth token
export TEST_AUTH_TOKEN="your-jwt-token"

# Optional: Change API URL for E2E tests
export API_URL="http://localhost:8080/api"
```

---

## Resources

- **FastAPI Testing Guide**: https://fastapi.tiangolo.com/tutorial/testing/
- **pytest Documentation**: https://docs.pytest.org/
- **pytest Markers**: https://docs.pytest.org/en/stable/how-to/mark.html
- **TestClient API**: https://fastapi.tiangolo.com/reference/testclient/

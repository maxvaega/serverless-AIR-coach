# Testing Documentation - AIR Coach API

## Test Strategy Overview

AIR Coach API uses a comprehensive testing approach with unit tests and end-to-end (E2E) integration tests.

### Test Categories

1. **Unit Tests**: Isolated component testing with mocks
2. **E2E Tests**: Full integration testing with running server
3. **Tool Tests**: Specific testing for LangGraph tools
4. **Cache Tests**: Google Cloud caching functionality

## Test Files Structure

```
tests/
├── conftest.py                     # Pytest configuration and fixtures
├── test_tools.py                   # Unit tests for domanda_teoria tool
├── test_stream_query.py            # E2E tests for streaming endpoint
├── test_update_docs.py             # E2E tests for document refresh
├── test_history_hook.py            # Unit tests for history management
├── test_history_window.py          # Window management tests
├── test_prompt_personalization.py # User prompt customization tests
├── test_caching.py                 # Google Cloud cache tests
└── readme.md                       # This documentation
```

## Running Tests

### Prerequisites

1. **Virtual Environment**: Activate before running tests
```bash
source .venv/bin/activate
```

2. **Environment Configuration**: Ensure `.env` file is properly configured
3. **MongoDB Access**: Required for E2E tests
4. **Running Server**: E2E tests require active backend server

### Test Commands

```bash
# Run all tests with verbose output
pytest -v -rs tests/

# Run specific test categories
pytest -v -rs tests/test_tools.py              # Unit tests only
pytest -v -rs tests/test_stream_query.py       # E2E streaming tests
pytest -v -rs tests/test_update_docs.py        # Document refresh tests
pytest -v -rs tests/test_caching.py            # Cache functionality tests

# Run tests with coverage
pytest --cov=src tests/

# Run specific test functions
pytest -v tests/test_tools.py::test_domanda_teoria_random
pytest -v tests/test_stream_query.py::test_stream_query_basic
```

## Test Execution Order

**IMPORTANT**: Always follow this sequence:

1. **Unit Tests First**: Run isolated tests with mocks
2. **Start Server**: Launch backend for E2E tests
3. **E2E Tests**: Run integration tests with live server
4. **Cleanup**: Stop server after E2E completion

## Unit Test Details

### Tool Testing (`test_tools.py`)
- **Purpose**: Test `domanda_teoria` tool functionality
- **Mocking**: Complete MongoDB isolation with mock data
- **Coverage**: All tool modes (random, chapter, specific, search)
- **Validation**: JSON output structure and content

### History Management (`test_history_hook.py`, `test_history_window.py`)
- **Purpose**: Test conversation memory management
- **Focus**: Rolling window, pre_model_hook functionality
- **Validation**: Message limitation and state preservation

### Prompt Personalization (`test_prompt_personalization.py`)
- **Purpose**: Test user-specific prompt generation
- **Mocking**: Auth0 user data simulation
- **Validation**: System prompt concatenation, user metadata injection

## E2E Test Details

### Streaming Tests (`test_stream_query.py`)
- **Requirements**: Running backend server
- **Authentication**: Auto-generated Auth0 tokens via `src.auth0.get_auth0_token()`
- **Validation**: Real streaming responses, tool integration
- **Coverage**: Full request-response cycle

### Document Update Tests (`test_update_docs.py`)
- **Purpose**: Test S3 document refresh functionality
- **Requirements**: AWS S3 access, document cache
- **Validation**: Document loading, prompt version updates

## Mock Strategy

### MongoDB Mocking
```python
# Unit tests use complete MongoDB isolation
@patch('src.database.get_questions_collection')
@patch('src.services.database.database_quiz_service.QuizMongoDBService')
```

### Auth0 Mocking
```python
# User data simulation for prompt personalization
mock_user_data = {
    "name": "Test User",
    "email": "test@example.com",
    "role": "student"
}
```

### S3 Mocking
```python
# Document loading simulation
mock_documents = ["content1", "content2"]
```

## Authentication for E2E Tests

E2E tests automatically generate valid Auth0 tokens:

```python
from src.auth0 import get_auth0_token

# Auto-generated token for testing
token = get_auth0_token()
headers = {"Authorization": f"Bearer {token}"}
```

## Test Data Management

### Quiz Test Data
- **Mock questions**: Structured JSON objects matching production schema
- **Chapter coverage**: Tests across all 10 theoretical chapters
- **Search scenarios**: Various text search patterns

### Conversation Test Data
- **Message history**: Simulated conversation flows
- **Thread scenarios**: Multiple user interactions
- **Memory states**: Various memory seeding situations

## Debugging Tests

### Verbose Output
```bash
# Maximum verbosity for debugging
pytest -v -s tests/test_name.py

# Capture print statements
pytest -s tests/test_name.py

# Stop on first failure
pytest -x tests/
```

### Common Issues

1. **E2E Test Failures**: Ensure backend server is running
2. **Auth Failures**: Check Auth0 configuration in `.env`
3. **MongoDB Issues**: Verify database connection
4. **Import Errors**: Confirm virtual environment activation

## Test Coverage Goals

- **Unit Tests**: >90% coverage for isolated components
- **Integration**: Full API endpoint coverage
- **Error Handling**: Exception scenarios and edge cases
- **Performance**: Response time validation for streaming

## Updating Tests

When modifying code:

1. **Update corresponding tests**: Maintain test-code synchronization
2. **Add new test cases**: Cover new functionality
3. **Update documentation**: Modify this file for test changes
4. **Verify coverage**: Ensure adequate test coverage maintained

## CI/CD Integration

Tests are designed for automated execution:
- **Fast unit tests**: Quick feedback in CI pipeline
- **Isolated E2E**: Separate environment for integration testing
- **Mock dependencies**: Reduced external dependencies for reliability
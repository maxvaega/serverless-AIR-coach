# API Reference Documentation

## Overview

AIR Coach API is a FastAPI-based application that provides intelligent chatbot interactions using Google's Gemini 2.0 Flash model. The API supports streaming responses, dynamic document context loading from AWS S3, and user metadata integration through Auth0.

**Base URL**: 
- Production: `https://www.air-coach.it/api`
- Development: `https://serverless-air-coach-git-develop-ai-struttore.vercel.app/api`
- Local: `http://localhost:8080/api`

## Authentication

All protected endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

See [Authentication Documentation](./authentication.md) for detailed authentication flow.

## Endpoints

### POST /api/stream_query

**Description**: Processes user queries and streams AI responses using Server-Sent Events (SSE).

**Authentication**: Required (JWT Bearer token)

**Request Format**:
```json
{
  "message": "string",
  "userid": "string"
}
```

**Request Model** (`MessageRequest`):
```python
class MessageRequest(BaseModel):
    message: str
    userid: str = Field(..., min_length=1)
```

**Request Parameters**:
- `message` (string, required): The user's query or message
- `userid` (string, required): User identifier in Auth0 format
  - Auth0 format: `auth0|[24 hex characters]`
  - Google OAuth2 format: `google-oauth2|[15-25 digits]`

**Response Format**: Server-Sent Events (SSE) stream

**SSE Response Structure**:
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"data": "First chunk of response"}

data: {"data": "Second chunk of response"}

data: {"data": "Final chunk of response"}

```

**SSE Data Format**:
Each SSE event contains a JSON object with a `data` field containing the response chunk:
```json
{"data": "Response text chunk"}
```

**Response Headers**:
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: *
```

**HTTP Status Codes**:
- `200 OK`: Successful streaming response
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: Token validation failed
- `422 Unprocessable Entity`: Invalid request payload
- `500 Internal Server Error`: Server-side processing error

**Example Request**:
```bash
curl -X POST "https://www.air-coach.it/api/stream_query" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the safety procedures for tandem jumps?",
    "userid": "auth0|507f1f77bcf86cd799439011"
  }'
```

**Example Response Stream**:
```
data: {"data": "Tandem skydiving safety procedures include several critical steps:\n\n1. **Pre-jump briefing**: "}

data: {"data": "Your instructor will explain body positioning, exit procedures, and emergency protocols.\n\n2. **Equipment check**: "}

data: {"data": "All gear including harnesses, altimeters, and parachutes are thoroughly inspected.\n\n3. **Altitude awareness**: "}

data: {"data": "Jumps typically occur from 10,000-15,000 feet with automatic activation devices as backup."}

```

**Features**:
- **Streaming Response**: Real-time response chunks via SSE
- **Chat History**: Includes last 10 conversations for context
- **User Metadata**: Integrates Auth0 user profile data
- **Dynamic Context**: Uses latest documents from S3 for system prompt

### POST /api/update_docs

**Description**: Manually refreshes the document cache from AWS S3 and regenerates the system prompt.

**Authentication**: Not required

**Request Format**: No request body required

**Response Format**:
```json
{
  "message": "string",
  "docs_count": "integer",
  "docs_details": [
    {
      "title": "string",
      "last_modified": "string"
    }
  ],
  "prompt_file": "object",
  "system_prompt": "string"
}
```

**Response Fields**:
- `message`: Success message indicating cache update
- `docs_count`: Total number of documents loaded from S3
- `docs_details`: Array of document metadata
  - `title`: Document filename
  - `last_modified`: Last modification timestamp (YYYY-MM-DD HH:MM:SS)
- `prompt_file`: S3 upload response object for the generated prompt file
- `system_prompt`: Complete system prompt text generated from documents

**HTTP Status Codes**:
- `200 OK`: Documents successfully updated
- `500 Internal Server Error`: S3 access error or prompt file creation failure

**Example Request**:
```bash
curl -X POST "https://www.air-coach.it/api/update_docs" \
  -H "Content-Type: application/json"
```

**Example Response**:
```json
{
  "message": "Documents cache updated successfully",
  "docs_count": 5,
  "docs_details": [
    {
      "title": "safety-procedures.md",
      "last_modified": "2024-01-15 10:30:00"
    },
    {
      "title": "equipment-guide.md", 
      "last_modified": "2024-01-14 15:45:00"
    }
  ],
  "prompt_file": {
    "ETag": "\"d41d8cd98f00b204e9800998ecf8427e\"",
    "ResponseMetadata": {
      "RequestId": "abc123",
      "HTTPStatusCode": 200
    }
  },
  "system_prompt": "You are an AI assistant specialized in skydiving and parachuting..."
}
```

## Data Models

### MessageRequest

```python
from pydantic import BaseModel, Field

class MessageRequest(BaseModel):
    message: str
    userid: str = Field(..., min_length=1)
```

**Validation Rules**:
- `message`: Any non-empty string
- `userid`: Must be at least 1 character, validated against Auth0/Google OAuth2 patterns

### MessageResponse

```python
class MessageResponse(BaseModel):
    query: str
    result: str
    userid: str = Field(..., min_length=1)
```

**Note**: This model is defined but not currently used in streaming responses. SSE responses use a simpler `{"data": "content"}` format.

## CORS Configuration

The API is configured with Cross-Origin Resource Sharing (CORS) to allow web applications to access the endpoints.

**Allowed Origins**:
```python
origins = [
    "http://localhost",
    "http://localhost:8080", 
    "http://localhost:8081"
]
```

**CORS Settings**:
- **Allow Credentials**: `true`
- **Allow Methods**: `["*"]` (all HTTP methods)
- **Allow Headers**: `["*"]` (all headers)

**Production CORS**: In production, origins should be restricted to specific domains for security.

## Rate Limiting and Timeouts

### Client Timeouts
- **Default Request Timeout**: 30 seconds (recommended for streaming)
- **Connection Timeout**: 10 seconds for initial connection

### Server-Side Limits
- **Streaming Timeout**: No explicit timeout (connection-dependent)
- **MongoDB Query Limit**: 10 messages for chat history
- **Cache Limits**:
  - User metadata cache: 1000 entries, 10-minute TTL
  - Auth0 token cache: 1 entry, 24-hour TTL

### Recommended Client Configuration

```javascript
// JavaScript example for streaming
const response = await fetch('/api/stream_query', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: userMessage,
    userid: userId
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      console.log(data.data); // Process response chunk
    }
  }
}
```

## Environment-Specific Features

### Development Mode
- **API Documentation**: Available at `/api/docs` (Swagger UI)
- **Debug Logging**: Enhanced logging for development
- **CORS**: Permissive localhost origins

### Production Mode
- **API Documentation**: Disabled (`docs_url=None`)
- **Logging**: Production-level logging only
- **CORS**: Should be restricted to specific domains
- **HTTPS**: Required for secure token transmission

**Environment Detection**:
```python
is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
docs_url = None if is_production else "/api/docs"
```

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error description"
}
```

### Common Error Scenarios

#### Authentication Errors
```json
// 401 Unauthorized
{
  "detail": "Requires authentication"
}

// 403 Forbidden  
{
  "detail": "Invalid token signature"
}
```

#### Validation Errors
```json
// 422 Unprocessable Entity
{
  "detail": [
    {
      "loc": ["body", "userid"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

#### Server Errors
```json
// 500 Internal Server Error
{
  "detail": "Internal server error"
}
```

### Error Handling in Streaming

During SSE streaming, errors are sent as data events:

```
data: {"error": "An error occurred while streaming the response: Connection timeout"}

```

## Performance Considerations

### Caching Strategy
- **Document Cache**: In-memory cache for S3 documents (manual refresh)
- **User Metadata Cache**: 10-minute TTL to reduce Auth0 API calls
- **Auth0 Token Cache**: 24-hour TTL for management tokens

### Optimization Features
- **Threading Locks**: Prevent concurrent document updates
- **Connection Pooling**: MongoDB and S3 client reuse
- **Lazy Loading**: Documents loaded on first request
- **Streaming**: Reduces perceived latency for long responses

### Monitoring

**Key Metrics to Monitor**:
- Response time for `/api/stream_query`
- Cache hit rates for user metadata and Auth0 tokens
- Document update frequency and S3 access patterns
- Authentication failure rates
- Streaming connection duration and completion rates

**Logging Integration**:
- **Langsmith Tracing**: Available when `LANGCHAIN_TRACING_V2=true`
- **Structured Logging**: JSON format for production monitoring
- **Request Tracking**: Token and user ID logging for debugging

## Security Considerations

### API Security
- **JWT Validation**: All tokens verified against Auth0 JWKS
- **HTTPS Only**: Required for production token transmission
- **CORS Policy**: Restrict origins in production
- **Input Validation**: Pydantic models validate all inputs

### Data Privacy
- **Token Logging**: Tokens are logged for debugging (consider masking in production)
- **User Data**: Metadata cached temporarily, not persisted long-term
- **Chat History**: Stored in MongoDB with user consent

### Best Practices
- Implement rate limiting per user/IP
- Monitor for unusual authentication patterns
- Regularly rotate Auth0 client secrets
- Use environment-specific CORS policies
- Enable request/response logging for security auditing

# Functional Analysis - AIR Coach API

**Audience**: Product managers, business stakeholders, end users
**Focus**: "WHAT IT DOES" (Business/Product perspective)

## Executive Summary

AIR Coach API is an intelligent chatbot platform designed to support theoretical training in paracadutismo (parachuting). The system provides a conversational interface for parachuting license exam preparation through:

- **Real-time chat interactions** with AI-powered responses
- **Structured quiz management** from exam question database
- **Dynamic content loading** from external educational sources
- **Personalized learning** adapted to user profiles

**Technology Stack**: Serverless deployment (Vercel) with Google Gemini 2.5 Flash LLM for contextual, accurate responses.

## Core Features

### 1. Interactive Streaming Chat

**User Experience:**
- Real-time AI-generated responses
- Response streaming for immediate feedback
- Persistent conversation memory across sessions
- Automatic educational context integration

**Use Cases:**
- Theoretical parachuting questions
- Regulations and procedures clarification
- Theoretical exam simulations
- Personalized educational support

### 2. Theoretical Quiz System

**Quiz Functionality:**
- **Random quizzes**: Questions from entire database for complete exam simulation
- **Chapter-specific quizzes**: Questions from specific theoretical chapters (1-10)
- **Direct question access**: Chapter and question number lookup
- **Text search**: Find questions by topic or keywords

**Available Chapters:**
1. Applied meteorology for parachuting
2. Applied aerodynamics for free-fall body
3. Equipment and instruments technology
4. Jump direction techniques
5. Parachute gliding techniques
6. General safety elements and procedures
7. Free-fall relative work safety procedures
8. Formation flying safety with gliding parachutes
9. Emergency situation procedures
10. Aeronautical regulations for parachuting

**Usage Examples:**
- "Let's simulate an exam quiz" → random question
- "Ask me a question from chapter 3" → random chapter question
- "Show me question 5 from chapter 2" → specific question
- "A question about VNE" → topic search

### 3. Dynamic Content Management

**Content Updates:**
- Automatic loading of educational files from AWS S3
- Manual refresh via dedicated endpoint
- Intelligent caching for optimal performance
- Content versioning for conversation isolation

**Benefits:**
- Always up-to-date content without service restart
- Centralized source for educational material
- Information consistency across sessions

### 4. User Personalization

**User Profile Integration:**
- Secure Auth0 authentication
- Automatic user metadata retrieval (name, email, role)
- Profile-based response personalization
- User data caching for improved performance

## API Endpoints

### 1. `/api/stream_query` (POST)
**Purpose**: Main endpoint for chat interactions
**Input**: User message and user ID
**Output**: Real-time response streaming
**Authentication**: Required (Bearer JWT Auth0)

**Streaming Response Format:**
```json
{"type": "agent_message", "data": "AI response text"}
{"type": "tool_result", "tool_name": "domanda_teoria", "data": {...}, "final": true}
```

### 2. `/api/update_docs` (POST)
**Purpose**: Manual refresh of educational context
**Input**: None
**Output**: Update status and document details
**Authentication**: None (public endpoint)

**Response Format:**
```json
{
  "message": "Documents updated successfully",
  "docs_count": 5,
  "docs_details": [...],
  "system_prompt": "...",
  "prompt_version": 3
}
```

### 3. `/api/test` (GET)
**Purpose**: Service health verification
**Output**: API status confirmation
**Authentication**: None

## Data Models

### MessageRequest
```python
{
  "message": str,      # User query text
  "userid": str        # User ID (required, minimum length 1)
}
```

### Quiz Structure
```json
{
  "capitolo": int,           # Chapter number (1-10)
  "capitolo_nome": str,      # Full chapter name
  "numero": int,             # Question number within chapter
  "testo": str,              # Question text
  "opzioni": [               # Options array
    {"id": "A", "testo": "..."},
    {"id": "B", "testo": "..."},
    {"id": "C", "testo": "..."}
  ],
  "risposta_corretta": str   # Correct option letter (e.g., "C")
}
```

## End-to-End User Flows

### Scenario 1: Theoretical Quiz
1. **Access**: User authenticates via Auth0
2. **Request**: "Ask me a theory question"
3. **Processing**: System selects random question from database
4. **Presentation**: Question displayed with multiple choice options
5. **Interaction**: User provides answer
6. **Feedback**: System validates and provides explanation if needed
7. **Continuation**: Option for more questions or follow-up

### Scenario 2: Educational Support
1. **Access**: Authenticated user starts conversation
2. **Question**: "What are the speed limits for parachutes?"
3. **Processing**: AI consults updated educational context
4. **Response**: Detailed information with regulatory references
5. **Follow-up**: Additional questions or clarifications

### Scenario 3: Exam Simulation
1. **Request**: "Let's simulate a theoretical exam"
2. **Multiple quizzes**: Series of random questions from all chapters
3. **Evaluation**: Feedback on each answer
4. **Final report**: Performance analysis and improvement areas

## Configuration

### Required Environment Variables
Reference `.env.example` for complete configuration:

**Essential:**
- `GOOGLE_API_KEY`: Access to Gemini models
- `MONGODB_URI`, `DATABASE_NAME`, `COLLECTION_NAME`: Database configuration
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`: S3 access
- `AUTH0_DOMAIN`, `AUTH0_SECRET`, `AUTH0_API_AUDIENCE`: Authentication

**Optional:**
- `FORCED_MODEL`: Specific LLM model (default: gemini-2.5-flash)
- `HISTORY_LIMIT`: Memory message limit (default: 10)
- `VERTEX_AI_REGION`: Google Cloud region (default: europe-west8)

## Security and Authentication

### Auth0 Authentication
- **JWT Bearer Token**: Verification via JWKS (JSON Web Key Set)
- **Audience validation**: Token recipient verification
- **Issuer validation**: Token issuer verification
- **Automatic expiration**: TTL token management

### Endpoint Protection
- `/api/stream_query`: **Protected** - Requires authentication
- `/api/update_docs`: **Public** - No authentication
- `/api/test`: **Public** - Health check

### Privacy and Compliance
- **EU Processing**: Processing in europe-west8 region (Milan)
- **Local cache**: User metadata cached locally (TTL 10 min)
- **Conversation isolation**: Separate threads per user and prompt version

## Testing and Quality

For complete testing documentation, see [`tests/readme.md`](../tests/readme.md).

**Test Coverage:**
- Unit tests for quiz functionality
- End-to-end tests for API endpoints
- Integration tests for streaming
- Complete mocks for dependency isolation

## Deployment and Environment

### Production Environment
- **Platform**: Vercel Serverless
- **Database**: MongoDB Atlas
- **Storage**: AWS S3
- **LLM**: Google Gemini 2.5 Flash
- **Authentication**: Auth0

### Monitoring
- **Structured logging**: Application events and errors
- **Performance metrics**: Latency and throughput
- **Health checks**: Status verification endpoint
- **Cache monitoring**: Google Cloud cache effectiveness

## Limitations and Considerations

### Technical Limitations
- **Volatile memory**: Depends on warm container for optimal performance
- **Concurrent users**: Limitations based on Vercel plan
- **Rate limiting**: Google API and MongoDB controls

### Usage Considerations
- **Internet connection**: Required for all functionality
- **Authentication**: Necessary for personalized functions
- **Browser compatibility**: SSE streaming support required
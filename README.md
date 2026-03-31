<div align="center">

# AIR Coach API

**AI-powered assistant for skydiving instructor training**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic-1C1C1C)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Real-world AI agent for a specialized, safety-critical domain — skydiving instructor qualification.*

</div>

---

## What is AIR Coach?

AIR Coach is a conversational AI agent designed to help skydiving instructors (AFF/tandem) prepare for theoretical exams and review safety protocols. It answers quiz questions, explains maneuvers, and adapts dynamically to the instructor's training progress.

Built as a **serverless FastAPI backend** deployed on **AWS Lambda**, it demonstrates how LangGraph agents can be deployed in production with real users, real data, and real domain constraints.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Lambda (FastAPI)                   │
│                                                           │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │  Auth0 JWT  │ -> │  LangGraph   │ -> │  Gemini 3   │ │
│  │  User info  │    │  Agent Graph │    │  Flash LLM  │ │
│  └─────────────┘    └──────┬───────┘    └─────────────┘ │
│                            │                              │
│                    ┌───────▼────────┐                    │
│                    │    MongoDB     │                    │
│                    │  Quiz DB +     │                    │
│                    │  Chat History  │                    │
│                    └───────────────┘                    │
│                                                           │
│  Context: .md files loaded dynamically from AWS S3       │
└─────────────────────────────────────────────────────────┘
```

**Stack:**
- **Runtime**: Python 3.10, FastAPI, Mangum (ASGI → Lambda)
- **AI**: LangGraph (stateful agent graph), Gemini 3 Flash
- **Data**: MongoDB (quiz questions, conversation state)
- **Auth**: Auth0 JWT validation (user context in system prompt)
- **Context**: AWS S3 (.md knowledge base, hot-reloadable)

**Key design decisions:**
- Rolling conversation window (`pre_model_hook`) — only last N turns sent to LLM, keeping costs low
- `domanda_teoria` tool for structured quiz retrieval and semantic search
- User identity injected into system prompt (not as chat messages)

---

## Getting Started

### Prerequisites

- Python 3.10+
- MongoDB instance (local or Atlas)
- Google Gemini API key
- Auth0 account (for user auth)
- AWS account (for Lambda deployment and S3)

### Local Development

```bash
git clone https://github.com/maxvaega/serverless-AIR-coach
cd serverless-AIR-coach
pip install -r requirements.txt
cp .env.example .env  # add your keys
python run.py
```

Server starts at `http://127.0.0.1:8080`.

### Environment Variables

See [.env.example](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Generative AI API key |
| `MONGODB_URI` | MongoDB connection string |
| `AUTH0_DOMAIN` | Auth0 domain for JWT validation |
| `S3_BUCKET` | S3 bucket for knowledge base .md files |
| `HISTORY_LIMIT` | Max conversation turns sent to LLM |

---

## Documentation

- **[Functional Analysis](docs/FUNCTIONAL.md)** — features, use cases, user flows
- **[Technical Analysis](docs/TECNICAL.md)** — architecture, patterns, implementation
- **[Testing](tests/README.md)** — testing strategy, pytest setup

---

## Monitoring

A built-in monitoring toolkit tracks:
- Token usage per session
- Knowledge base cache effectiveness
- API cost estimates
- Rate limit exposure

See `scripts/count_tokens.py` for the token analyzer.

---

## Author

**Massimo Vaega** · [LinkedIn](https://www.linkedin.com/in/massimoolivieri/) · [GitHub](https://github.com/maxvaega)

*AI Discovery Leader — building AI agents that actually work in production.*

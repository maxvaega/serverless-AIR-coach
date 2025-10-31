from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Any, Optional

# Define request/response models

class MessageRequest(BaseModel):
    """
    Request model for streaming query endpoint.

    Attributes:
        message: User query text
        userid: User identifier (required, minimum length 1)
    """
    message: str = Field(..., description="User query text")
    userid: str = Field(..., min_length=1, description="User identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Ciao cosa sai dirmi?",
                "userid": "userid_string"
            }
        }

class MessageResponse(BaseModel):
    query: str
    result: str
    userid: str = Field(..., min_length=1)


# SSE Event Models for /stream_query

class SSEAgentMessage(BaseModel):
    """
    SSE event for incremental agent text response chunks.

    These events are streamed continuously as the AI generates the response.
    Clients should concatenate all chunks to build the complete response.
    """
    type: Literal["agent_message"] = "agent_message"
    data: str = Field(..., description="Text chunk from AI response")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "agent_message",
                "data": "Ciao! Sono AIR Coach, sono qui per aiutarti con le tue domande sul paracadutismo..."
            }
        }


class QuizOption(BaseModel):
    """Quiz answer option structure."""
    id: str = Field(..., description="Option identifier (A, B, C, D)")
    testo: str = Field(..., description="Option text")


class QuizQuestion(BaseModel):
    """
    Quiz question structure returned by domanda_teoria tool.

    Represents a complete parachuting theory exam question with multiple choice options.
    """
    capitolo: int = Field(..., ge=1, le=10, description="Chapter number (1-10)")
    capitolo_nome: str = Field(..., description="Full chapter name")
    numero: int = Field(..., description="Question number within chapter")
    testo: str = Field(..., description="Question text")
    opzioni: List[QuizOption] = Field(..., description="Answer options (typically 3-4 options)")
    risposta_corretta: str = Field(..., description="Correct answer letter (A, B, C, or D)")

    class Config:
        json_schema_extra = {
            "example": {
                "capitolo": 3,
                "capitolo_nome": "Tecnologia degli equipaggiamenti e strumenti in uso",
                "numero": 5,
                "testo": "Qual è la VNE (Velocity Never Exceed) del paracadute principale?",
                "opzioni": [
                    {"id": "A", "testo": "100 km/h"},
                    {"id": "B", "testo": "120 km/h"},
                    {"id": "C", "testo": "140 km/h"}
                ],
                "risposta_corretta": "B"
            }
        }


class SSEToolResult(BaseModel):
    """
    SSE event for tool execution result.

    Sent when the AI agent executes a tool (e.g., domanda_teoria for quiz questions).
    The data structure depends on the specific tool being executed.
    """
    type: Literal["tool_result"] = "tool_result"
    tool_name: str = Field(..., description="Name of the executed tool")
    data: Dict[str, Any] = Field(..., description="Tool output (structure depends on tool type)")
    final: bool = Field(True, description="Indicates completion of tool execution")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "tool_result",
                "tool_name": "domanda_teoria",
                "data": {
                    "capitolo": 1,
                    "capitolo_nome": "Meteorologia applicata al paracadutismo",
                    "numero": 3,
                    "testo": "A quale quota si formano generalmente i cumuli?",
                    "opzioni": [
                        {"id": "A", "testo": "1000-2000 metri"},
                        {"id": "B", "testo": "2000-4000 metri"},
                        {"id": "C", "testo": "4000-6000 metri"}
                    ],
                    "risposta_corretta": "A"
                },
                "final": True
            }
        }


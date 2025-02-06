from pydantic import BaseModel
from typing import Optional

# Define response model

class MessageRequest(BaseModel):
    message: str
    userid: Optional[str] = None

class MessageResponse(BaseModel):
    query: str
    result: str
    userid: str

class DatabaseInput(BaseModel):
    human: str
    system: str
    userid: str
    env : str
    timestamp : str
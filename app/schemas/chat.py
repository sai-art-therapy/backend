from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    child_id: Optional[str] = None
    report_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    safety_notice: str
from datetime import datetime

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    id: str = Field(..., description="Session id")
    user_id: int = Field(..., description="Session owner id")
    title: str
    created_at: datetime
    updated_at: datetime


class CreateSession(BaseModel):
    id: str = Field(..., description="Client-generated session id")
    title: str = Field(..., description="Session title")

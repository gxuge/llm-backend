from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Role = Literal["user", "assistant", "tool", "system"]


class SessionMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, description="Message id")
    session_id: str = Field(..., description="Conversation/session id")
    user_id: int | None = Field(None, description="Message owner id")
    role: Role
    content: str
    reasoning: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parent_id: str | None = Field(None, description="Optional parent message id")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSessionMessage(BaseModel):
    role: Role
    content: str
    reasoning: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateSessionMessage(BaseModel):
    content: str | None = None
    reasoning: str | None = None
    metadata: dict[str, Any] | None = None


class SessionChatResponse(BaseModel):
    session_id: str
    model: str
    content: str
    reasoning: str | None = None
    raw: dict[str, Any] | None = None

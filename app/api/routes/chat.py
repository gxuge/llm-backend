import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.repositories.chroma_repository import chroma_repository_dependency
from app.api.deps import get_current_user
from app.schemas.chat import CreateSessionMessage, SessionMessage, UpdateSessionMessage
from app.schemas.session import CreateSession, SessionInfo
from app.services.chat_service import chat_service
from app.services.modelscope import (
    ModelscopeChatError,
    create_chat_completion,
    stream_chat_completion,
)

router = APIRouter(tags=["Chat"])
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role, e.g. user/assistant/system")
    content: str = Field(..., description="Plain text content")


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        None, description="Conversation id for grouping history"
    )
    session_id: str | None = Field(
        None, description="Session id for grouping history (use stored messages)"
    )
    model: str | None = Field(None, description="ModelScope model name")
    messages: list[ChatMessage] | None = Field(None, description="Ordered chat messages")
    api_key: str | None = Field(
        None, description="Optional API key to override the server-side default"
    )
    temperature: float | None = Field(None, ge=0, le=2)
    top_p: float | None = Field(None, ge=0, le=1)
    presence_penalty: float | None = Field(None, ge=-2, le=2)
    frequency_penalty: float | None = Field(None, ge=-2, le=2)
    max_tokens: int | None = Field(None, ge=1)
    stream: bool | None = Field(None, description="Whether to request a streaming response")


class ChatResponse(BaseModel):
    conversation_id: str
    model: str
    content: str
    reasoning: str | None = None
    raw: dict | None = None


class DeepseekParams(BaseModel):
    api_key: str | None = Field(
        None, description="Optional API key to override the server-side default"
    )
    temperature: float | None = Field(None, ge=0, le=2)
    top_p: float | None = Field(None, ge=0, le=1)
    presence_penalty: float | None = Field(None, ge=-2, le=2)
    frequency_penalty: float | None = Field(None, ge=-2, le=2)
    max_tokens: int | None = Field(None, ge=1)
    stream: bool | None = Field(None, description="Whether to request a streaming response")


def _merge_generation_params(payload: ChatRequest | DeepseekParams) -> dict:
    """
    Apply server defaults for generation params so the backend behaves
    similarly to Lobechat's configurable provider pattern.
    """
    return {
        "api_key": getattr(payload, "api_key", None),
        "temperature": (
            payload.temperature
            if payload.temperature is not None
            else settings.model_temperature_default
        ),
        "top_p": payload.top_p if payload.top_p is not None else settings.model_top_p_default,
        "presence_penalty": (
            payload.presence_penalty
            if payload.presence_penalty is not None
            else settings.model_presence_penalty_default
        ),
        "frequency_penalty": (
            payload.frequency_penalty
            if payload.frequency_penalty is not None
            else settings.model_frequency_penalty_default
        ),
        "max_tokens": (
            payload.max_tokens if payload.max_tokens is not None else settings.model_max_tokens_default
        ),
        "stream": payload.stream if payload.stream is not None else settings.model_stream_default,
    }


@router.post(
    "/chat/completions",
    summary="Proxy ModelScope chat completions",
    response_model=ChatResponse,
)
async def chat_completions(
    payload: ChatRequest,
    chroma_repo=Depends(chroma_repository_dependency),
    current_user=Depends(get_current_user),
) -> ChatResponse:
    model = payload.model or settings.model_default
    if payload.session_id:
        generation_params = _merge_generation_params(payload)
        if generation_params.get("stream"):
            history = chat_service.list_messages(payload.session_id, current_user.id)
            prompt = [
                {"role": message.role, "content": message.content} for message in history
            ]
            stream = await stream_chat_completion(prompt, model=model, **generation_params)
            return StreamingResponse(stream, media_type="text/event-stream")
        try:
            result = await chat_service.chat_with_model(
                session_id=payload.session_id,
                user_id=current_user.id,
                model=model,
                **generation_params
            )
        except ModelscopeChatError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unhandled chat session error")
            raise HTTPException(status_code=500, detail="Unexpected chat proxy error") from exc

        conversation_id = payload.conversation_id or payload.session_id
        return ChatResponse(
            conversation_id=conversation_id,
            model=model,
            content=result.content,
            reasoning=result.reasoning,
            raw=result.raw,
        )

    if not payload.messages or not payload.conversation_id:
        raise HTTPException(status_code=400, detail="messages and conversation_id are required")

    messages = [message.model_dump() for message in payload.messages]
    generation_params = _merge_generation_params(payload)
    if generation_params.get("stream"):
        stream = await stream_chat_completion(messages, model=model, **generation_params)
        return StreamingResponse(stream, media_type="text/event-stream")
    try:
        result = await create_chat_completion(messages, model=model, **generation_params)
    except ModelscopeChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unhandled chat proxy error")
        raise HTTPException(status_code=500, detail="Unexpected chat proxy error") from exc

    try:
        chroma_repo.add_conversation_record(
            payload.conversation_id,
            model,
            messages,
            result["content"],
            result.get("reasoning"),
        )
    except Exception as exc:  # pragma: no cover - storage is best-effort
        logger.warning("Chroma add failed: %s", exc)

    return ChatResponse(
        conversation_id=payload.conversation_id,
        model=model,
        content=result["content"],
        reasoning=result.get("reasoning"),
        raw=result.get("raw"),
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[SessionMessage],
    summary="List messages for a session",
)
async def list_messages(
    session_id: str, current_user=Depends(get_current_user)
) -> list[SessionMessage]:
    return chat_service.list_messages(session_id, current_user.id)


@router.get(
    "/sessions",
    response_model=list[SessionInfo],
    summary="List sessions for current user",
)
async def list_sessions(current_user=Depends(get_current_user)) -> list[SessionInfo]:
    return chat_service.session_repo.list_by_user(current_user.id)


@router.post(
    "/sessions",
    response_model=SessionInfo,
    status_code=201,
    summary="Create a session",
)
async def create_session(
    payload: CreateSession, current_user=Depends(get_current_user)
) -> SessionInfo:
    existing = chat_service.session_repo.get(payload.id, current_user.id)
    if existing:
        return existing
    return chat_service.session_repo.create(payload.id, current_user.id, payload.title)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SessionMessage,
    status_code=201,
    summary="Create a message inside a session",
)
async def create_message(
    session_id: str,
    payload: CreateSessionMessage,
    current_user=Depends(get_current_user),
) -> SessionMessage:
    return chat_service.create_message(session_id, current_user.id, payload)


@router.patch(
    "/messages/{message_id}",
    response_model=SessionMessage,
    summary="Update an existing message",
)
async def update_message(
    message_id: str,
    payload: UpdateSessionMessage,
    current_user=Depends(get_current_user),
) -> SessionMessage:
    try:
        return chat_service.update_message(message_id, current_user.id, payload)
    except ValueError:
        raise HTTPException(status_code=404, detail="message not found")


@router.delete("/messages/{message_id}", status_code=204, summary="Delete a message")
async def delete_message(message_id: str, current_user=Depends(get_current_user)) -> None:
    try:
        chat_service.delete_message(message_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="message not found")
    return None

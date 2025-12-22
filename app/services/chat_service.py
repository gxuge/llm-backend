import logging
import re

from app.core.config import settings
from app.repositories.message_repository import MessageRepository, message_repository
from app.repositories.session_repository import SessionRepository, session_repository
from app.schemas.chat import (
    CreateSessionMessage,
    SessionChatResponse,
    SessionMessage,
    UpdateSessionMessage,
)
from app.services.modelscope import create_chat_completion

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, message_repo: MessageRepository, session_repo: SessionRepository) -> None:
        self.message_repo = message_repo
        self.session_repo = session_repo

    def list_messages(self, session_id: str, user_id: int) -> list[SessionMessage]:
        return self.message_repo.list_by_session(session_id, user_id)

    def create_message(
        self, session_id: str, user_id: int, payload: CreateSessionMessage
    ) -> SessionMessage:
        if not self.session_repo.get(session_id, user_id):
            title = payload.content.strip()[:48] or "New Conversation"
            self.session_repo.create(session_id, user_id, title)
        else:
            self.session_repo.touch(session_id, user_id)
        payload_data = payload.model_dump()
        content = payload_data.get("content") or ""
        metadata = payload_data.get("metadata") or {}
        reasoning = payload_data.get("reasoning")
        if reasoning is None and "reasoning" in metadata:
            reasoning = metadata.get("reasoning")
            metadata = {key: value for key, value in metadata.items() if key != "reasoning"}
        content, reasoning = self._split_think_content(content, reasoning)
        payload_data["content"] = content
        payload_data["reasoning"] = reasoning
        payload_data["metadata"] = metadata
        message = SessionMessage(session_id=session_id, user_id=user_id, **payload_data)
        return self.message_repo.add(message)

    def update_message(
        self, message_id: str, user_id: int, payload: UpdateSessionMessage
    ) -> SessionMessage:
        payload_data = payload.model_dump()
        metadata = payload_data.get("metadata")
        if payload_data.get("reasoning") is None and metadata and "reasoning" in metadata:
            payload_data["reasoning"] = metadata.get("reasoning")
            payload_data["metadata"] = {key: value for key, value in metadata.items() if key != "reasoning"}
        if payload_data.get("content") is not None:
            content, reasoning = self._split_think_content(
                payload_data.get("content") or "", payload_data.get("reasoning")
            )
            payload_data["content"] = content
            payload_data["reasoning"] = reasoning
        try:
            return self.message_repo.update(
                message_id,
                content=payload_data.get("content"),
                reasoning=payload_data.get("reasoning"),
                metadata=payload_data.get("metadata"),
                user_id=user_id,
            )
        except ValueError as exc:
            raise exc

    def delete_message(self, message_id: str, user_id: int) -> None:
        self.message_repo.delete(message_id, user_id=user_id)

    @staticmethod
    def _build_prompt(messages: list[SessionMessage]) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in messages]

    @staticmethod
    def _split_think_content(content: str, reasoning: str | None) -> tuple[str, str | None]:
        if not content:
            return content, reasoning
        match = re.search(r"<think>(.*?)</think>", content, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return content, reasoning
        extracted = match.group(1).strip()
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
        if reasoning:
            return cleaned, reasoning
        return cleaned, extracted or reasoning

    async def chat_with_model(
        self,
        *,
        session_id: str,
        user_id: int,
        model: str,
        api_key: str | None,
        temperature: float | None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> SessionChatResponse:
        history = self.list_messages(session_id, user_id)
        prompt = self._build_prompt(history)

        result = await create_chat_completion(
            prompt,
            model=model,
            api_key=api_key,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            max_tokens=max_tokens,
            stream=stream,
        )

        return SessionChatResponse(
            session_id=session_id,
            model=model,
            content=result["content"],
            reasoning=result.get("reasoning"),
            raw=result.get("raw"),
        )


chat_service = ChatService(message_repo=message_repository, session_repo=session_repository)
DEEPSEEK_R1 = settings.model_deepseek_r1
DEEPSEEK_V32 = settings.model_deepseek_v3_2

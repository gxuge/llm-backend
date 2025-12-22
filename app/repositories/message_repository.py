import json
from typing import Iterable

from app.db import db_connection
from app.schemas.chat import SessionMessage


class MessageRepository:
    def list_by_session(self, session_id: str, user_id: int) -> list[SessionMessage]:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, user_id, role, content, reasoning, created_at, parent_id, metadata
                FROM messages
                WHERE session_id = ? AND user_id = ?
                ORDER BY created_at ASC
                """,
                (session_id, user_id),
            ).fetchall()
        messages: list[SessionMessage] = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            reasoning = row["reasoning"]
            if reasoning is None and "reasoning" in metadata:
                reasoning = metadata.get("reasoning")
                metadata = {key: value for key, value in metadata.items() if key != "reasoning"}
            messages.append(
                SessionMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                    role=row["role"],
                    content=row["content"],
                    reasoning=reasoning,
                    created_at=row["created_at"],
                    parent_id=row["parent_id"],
                    metadata=metadata,
                )
            )
        return messages

    def add(self, message: SessionMessage) -> SessionMessage:
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, session_id, user_id, role, content, reasoning, created_at, parent_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.user_id,
                    message.role,
                    message.content,
                    message.reasoning,
                    message.created_at,
                    message.parent_id,
                    json.dumps(message.metadata, ensure_ascii=False),
                ),
            )
        return message

    def update(
        self,
        message_id: str,
        *,
        content: str | None,
        reasoning: str | None,
        metadata: dict | None,
        user_id: int,
    ) -> SessionMessage:
        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT id, session_id, user_id, role, content, reasoning, created_at, parent_id, metadata
                FROM messages
                WHERE id = ? AND user_id = ?
                """,
                (message_id, user_id),
            ).fetchone()
            if not row:
                raise ValueError("message not found")

            new_content = content if content is not None else row["content"]
            new_reasoning = reasoning if reasoning is not None else row["reasoning"]
            new_metadata = (
                metadata if metadata is not None else json.loads(row["metadata"]) if row["metadata"] else {}
            )
            conn.execute(
                """
                UPDATE messages
                SET content = ?, reasoning = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    new_content,
                    new_reasoning,
                    json.dumps(new_metadata, ensure_ascii=False),
                    message_id,
                ),
            )

        return SessionMessage(
            id=row["id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            role=row["role"],
            content=new_content,
            reasoning=new_reasoning,
            created_at=row["created_at"],
            parent_id=row["parent_id"],
            metadata=new_metadata,
        )

    def delete(self, message_id: str, *, user_id: int) -> None:
        with db_connection() as conn:
            result = conn.execute(
                "DELETE FROM messages WHERE id = ? AND user_id = ?",
                (message_id, user_id),
            )
            if result.rowcount == 0:
                raise ValueError("message not found")

    def extend(self, messages: Iterable[SessionMessage]) -> None:
        for message in messages:
            self.add(message)


message_repository = MessageRepository()

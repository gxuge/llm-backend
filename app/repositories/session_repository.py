from datetime import datetime

from app.db import db_connection
from app.schemas.session import SessionInfo


class SessionRepository:
    def list_by_user(self, user_id: int) -> list[SessionInfo]:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            SessionInfo(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get(self, session_id: str, user_id: int) -> SessionInfo | None:
        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM sessions
                WHERE id = ? AND user_id = ?
                """,
                (session_id, user_id),
            ).fetchone()
        if not row:
            return None
        return SessionInfo(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, session_id: str, user_id: int, title: str) -> SessionInfo:
        now = datetime.utcnow().isoformat()
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, title, now, now),
            )
        return SessionInfo(
            id=session_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

    def touch(self, session_id: str, user_id: int, *, title: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with db_connection() as conn:
            if title is not None:
                conn.execute(
                    """
                    UPDATE sessions
                    SET title = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (title, now, session_id, user_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE sessions
                    SET updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (now, session_id, user_id),
                )


session_repository = SessionRepository()

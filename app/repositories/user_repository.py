from dataclasses import dataclass
from datetime import datetime

from app.db import db_connection


@dataclass
class UserRecord:
    id: int
    username: str
    password_hash: str
    created_at: str


class UserRepository:
    def create_user(self, username: str, password_hash: str) -> UserRecord:
        created_at = datetime.utcnow().isoformat()
        with db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (username, password_hash, created_at),
            )
            user_id = cursor.lastrowid
        return UserRecord(id=user_id, username=username, password_hash=password_hash, created_at=created_at)

    def get_by_username(self, username: str) -> UserRecord | None:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return UserRecord(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )

    def get_by_id(self, user_id: int) -> UserRecord | None:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return UserRecord(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )


user_repository = UserRepository()

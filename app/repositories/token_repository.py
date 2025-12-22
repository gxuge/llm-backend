from dataclasses import dataclass
from datetime import datetime

from app.db import db_connection


@dataclass
class TokenRecord:
    id: int
    user_id: int
    token: str
    created_at: str


class TokenRepository:
    def create_token(self, user_id: int, token: str) -> TokenRecord:
        created_at = datetime.utcnow().isoformat()
        with db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tokens (user_id, token, created_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token, created_at),
            )
            token_id = cursor.lastrowid
        return TokenRecord(id=token_id, user_id=user_id, token=token, created_at=created_at)

    def get_by_token(self, token: str) -> TokenRecord | None:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT id, user_id, token, created_at FROM tokens WHERE token = ?",
                (token,),
            ).fetchone()
        if not row:
            return None
        return TokenRecord(
            id=row["id"],
            user_id=row["user_id"],
            token=row["token"],
            created_at=row["created_at"],
        )

    def delete_token(self, token: str) -> None:
        with db_connection() as conn:
            conn.execute("DELETE FROM tokens WHERE token = ?", (token,))


token_repository = TokenRepository()

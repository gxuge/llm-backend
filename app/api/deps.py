from fastapi import Header, HTTPException

from app.repositories.token_repository import token_repository
from app.repositories.user_repository import user_repository


def get_current_user(authorization: str | None = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = authorization.split(" ", 1)[1].strip()
    token_record = token_repository.get_by_token(token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = user_repository.get_by_id(token_record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user

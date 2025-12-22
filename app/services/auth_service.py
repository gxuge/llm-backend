import hashlib
import hmac
import secrets
from dataclasses import dataclass

from app.repositories.token_repository import token_repository
from app.repositories.user_repository import user_repository


@dataclass
class AuthUser:
    id: int
    username: str


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${_hash_password(password, salt)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored = password_hash.split("$", 1)
    except ValueError:
        return False
    computed = _hash_password(password, salt)
    return hmac.compare_digest(stored, computed)


def register_user(username: str, password: str) -> AuthUser:
    existing = user_repository.get_by_username(username)
    if existing:
        raise ValueError("username already exists")
    record = user_repository.create_user(username, hash_password(password))
    return AuthUser(id=record.id, username=record.username)


def authenticate_user(username: str, password: str) -> AuthUser | None:
    record = user_repository.get_by_username(username)
    if not record or not verify_password(password, record.password_hash):
        return None
    return AuthUser(id=record.id, username=record.username)


def issue_token(user_id: int) -> str:
    token = secrets.token_hex(32)
    token_repository.create_token(user_id, token)
    return token

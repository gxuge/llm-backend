from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.auth_service import authenticate_user, issue_token, register_user

router = APIRouter(tags=["Auth"])


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: AuthRequest) -> AuthResponse:
    try:
        user = register_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token = issue_token(user.id)
    return AuthResponse(token=token, user={"id": user.id, "username": user.username})


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthRequest) -> AuthResponse:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = issue_token(user.id)
    return AuthResponse(token=token, user={"id": user.id, "username": user.username})


@router.get("/auth/me")
def me(current_user=Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}

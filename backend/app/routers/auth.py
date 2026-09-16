"""API routes cho Authentication (docs/auth-spec.md) — register/login/logout/me."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import (
    JWT_EXPIRE_MINUTES,
    create_access_token,
    decode_access_token,
    get_cookie_settings,
    hash_password,
    normalize_email,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"
FRONTEND_URL = os.getenv("FRONTEND_URL")


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _set_auth_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    settings = get_cookie_settings(FRONTEND_URL)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        path="/",
        max_age=JWT_EXPIRE_MINUTES * 60,
        secure=settings["secure"],
        samesite=settings["samesite"],
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Chưa đăng nhập")

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(401, "Chưa đăng nhập")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Chưa đăng nhập")
    return user


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)


@router.post("/register", status_code=201, response_model=UserOut)
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user = User(
        email=normalize_email(req.email),
        password_hash=hash_password(req.password),
        display_name=req.display_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email đã được đăng ký")

    db.refresh(user)
    _set_auth_cookie(response, user.id)
    return user


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=UserOut)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(req.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")

    _set_auth_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, current_user: User = Depends(get_current_user)):
    settings = get_cookie_settings(FRONTEND_URL)
    response.delete_cookie(
        key=COOKIE_NAME, path="/", secure=settings["secure"], samesite=settings["samesite"]
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

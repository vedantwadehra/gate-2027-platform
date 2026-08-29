from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import (
    create_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.db import models
from app.api.deps import get_current_user

auth = APIRouter()


class RegisterReq(BaseModel):
    email: str
    name: str | None = None
    password: str


class LoginReq(BaseModel):
    email: str
    password: str


class TokenRes(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _public_user(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name}


@auth.post("/auth/register", response_model=TokenRes)
def register(payload: RegisterReq, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenRes(
        access_token=create_token(user.id, user.email, user.is_admin), user=_public_user(user)
    )


@auth.post("/auth/login", response_model=TokenRes)
def login(payload: LoginReq, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash or ""):
        raise HTTPException(401, "Invalid email or password")
    return TokenRes(
        access_token=create_token(user.id, user.email, user.is_admin), user=_public_user(user)
    )


@auth.get("/me")
def me(user: dict | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user

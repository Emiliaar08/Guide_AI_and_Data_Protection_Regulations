"""Аккаунты и сессии: регистрация, вход, проверка сессии, выход.

Спецификация: spec/tech/architecture.md, раздел «Аккаунты и рабочее пространство».
Сессия хранится в Redis, браузер получает cookie session_id (HttpOnly).
"""
import hashlib
import hmac
import os
import secrets
from typing import Annotated

import redis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import db

SESSION_TTL = 3600  # секунд; продлевается при каждом запросе вошедшего пользователя
COOKIE = "session_id"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
UNAVAILABLE = "Аккаунты временно недоступны"

_redis = None


# ---------- пароли ----------

def hash_password(password: str) -> str:
    """scrypt с индивидуальной солью. Формат: scrypt$N$r$p$соль$хэш (hex)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        candidate = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest))
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest)


# хэш-пустышка: при неизвестной почте проверка занимает столько же времени, сколько при неверном пароле
DUMMY_HASH = hash_password("not-a-real-password")


# ---------- хранилище ----------

def redis_client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _redis


def require_storage() -> None:
    """Без DATABASE_URL и REDIS_URL аккаунты отключены: 503, интерфейс работает как гостевой."""
    if not (db.enabled() and os.getenv("REDIS_URL")):
        raise HTTPException(status_code=503, detail=UNAVAILABLE)


def get_db():
    session = db.session_factory()()
    try:
        yield session
    finally:
        session.close()


def _set_cookie(response: Response, token: str) -> None:
    # Secure не ставим: локальный запуск идёт по http://localhost
    response.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="lax", path="/")


def _start_session(response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    try:
        redis_client().set(f"session:{token}", user_id, ex=SESSION_TTL)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from exc
    _set_cookie(response, token)


def get_current_user(
    response: Response,
    _: None = Depends(require_storage),
    session_id: str | None = Cookie(default=None),
    session: Session = Depends(get_db),
) -> db.User:
    """Вошедший пользователь по cookie. Пригодится маршрутам рабочего пространства."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Требуется вход")
    try:
        r = redis_client()
        user_id = r.get(f"session:{session_id}")
        if user_id:
            r.expire(f"session:{session_id}", SESSION_TTL)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from exc
    user = session.get(db.User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется вход")
    _set_cookie(response, session_id)  # продлеваем cookie вместе с сессией
    return user


# ---------- маршруты ----------

router = APIRouter(prefix="/api/auth", dependencies=[Depends(require_storage)])


class RegisterRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _public(user: db.User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/register", status_code=201)
def register(req: RegisterRequest, response: Response, session: Session = Depends(get_db)) -> dict:
    email = req.email.lower()
    if session.scalar(select(db.User).where(db.User.email == email)):
        raise HTTPException(status_code=409, detail="Эта почта уже зарегистрирована")
    user = db.User(name=req.name, email=email, password_hash=hash_password(req.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # две регистрации одной почты одновременно
        session.rollback()
        raise HTTPException(status_code=409, detail="Эта почта уже зарегистрирована") from exc
    _start_session(response, user.id)
    return {"user": _public(user)}


@router.post("/login")
def login(req: LoginRequest, response: Response, session: Session = Depends(get_db)) -> dict:
    user = session.scalar(select(db.User).where(db.User.email == req.email.lower()))
    password_ok = verify_password(req.password, user.password_hash if user else DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Неверная почта или пароль")
    _start_session(response, user.id)
    return {"user": _public(user)}


@router.get("/me")
def me(user: db.User = Depends(get_current_user)) -> dict:
    return {"user": _public(user)}


@router.post("/logout", status_code=204)
def logout(session_id: str | None = Cookie(default=None)) -> Response:
    if session_id:
        try:
            redis_client().delete(f"session:{session_id}")
        except redis.RedisError:
            pass  # сессия всё равно истечёт сама
    result = Response(status_code=204)
    result.delete_cookie(COOKIE, path="/")
    return result

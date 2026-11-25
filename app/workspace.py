"""Рабочее пространство вошедшего пользователя: история чатов и избранное.

Спецификация: spec/tech/architecture.md, раздел «Аккаунты и рабочее пространство».
Все маршруты требуют сессию (401), без хранилища отвечают 503.
"""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import db
from .accounts import get_current_user, get_db

CHAT_ID = r"^[A-Za-z0-9_-]{1,64}$"
ARTICLE_ID = r"^[A-Za-z0-9:._-]{1,64}$"
MAX_MESSAGES = 200
MAX_TEXT = 20000

ChatIdPath = Annotated[str, Path(pattern=CHAT_ID)]
MessageIdPath = Annotated[str, Path(pattern=CHAT_ID)]
ArticleIdPath = Annotated[str, Path(pattern=ARTICLE_ID)]


# ---------- время ----------

def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    """Формат как у JavaScript (toISOString): 2026-11-26T10:00:00.123Z."""
    value = utc(value)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


# ---------- входные данные ----------

class MessageIn(BaseModel):
    id: str = Field(pattern=CHAT_ID)
    role: Literal["user", "assistant"]
    text: str = Field(max_length=MAX_TEXT)
    jurisdiction: Literal["ru", "eu"] | None = None
    createdAt: datetime
    status: Literal["pending", "sent", "error", "interrupted"] = "sent"
    errorText: str | None = Field(default=None, max_length=2000)
    citations: list[dict] = Field(default_factory=list, max_length=20)
    replyStatus: Literal["ok", "need_clarification", "insufficient"] | None = None


class ChatIn(BaseModel):
    id: str | None = Field(default=None, pattern=CHAT_ID)
    title: str = Field(default="", max_length=200)
    jurisdiction: Literal["", "ru", "eu"] | None = ""
    createdAt: datetime
    updatedAt: datetime
    messages: list[MessageIn] = Field(max_length=MAX_MESSAGES)


class FavoriteAnswerIn(BaseModel):
    chatId: str | None = Field(default=None, pattern=CHAT_ID)
    question: str = Field(max_length=2000)
    message: MessageIn
    savedAt: datetime


# ---------- ответы ----------

def message_json(m: MessageIn) -> dict:
    """Сообщение в формате интерфейса; незавершённое (pending) сохраняется как interrupted."""
    data = {
        "id": m.id, "role": m.role, "text": m.text, "jurisdiction": m.jurisdiction,
        "createdAt": iso(m.createdAt),
        "status": "interrupted" if m.status == "pending" else m.status,
        "citations": m.citations,
    }
    if m.errorText is not None:
        data["errorText"] = m.errorText
    if m.replyStatus is not None:
        data["replyStatus"] = m.replyStatus
    return data


def message_row_json(row: db.Message) -> dict:
    data = {
        "id": row.id, "role": row.role, "text": row.text, "jurisdiction": row.jurisdiction,
        "createdAt": iso(row.created_at), "status": row.status, "citations": row.citations,
    }
    if row.error_text is not None:
        data["errorText"] = row.error_text
    if row.reply_status is not None:
        data["replyStatus"] = row.reply_status
    return data


def chat_json(chat: db.Chat, messages: list[dict]) -> dict:
    return {
        "id": chat.id, "title": chat.title, "jurisdiction": chat.jurisdiction,
        "createdAt": iso(chat.created_at), "updatedAt": iso(chat.updated_at), "messages": messages,
    }


def load_messages(session: Session, user_id: str, chat_id: str) -> list[dict]:
    rows = session.scalars(
        select(db.Message).where(db.Message.user_id == user_id, db.Message.chat_id == chat_id).order_by(db.Message.position)
    ).all()
    return [message_row_json(row) for row in rows]


# ---------- маршруты ----------

router = APIRouter(prefix="/api")


@router.get("/workspace")
def get_workspace(user: db.User = Depends(get_current_user), session: Session = Depends(get_db)) -> dict:
    chats = session.scalars(
        select(db.Chat).where(db.Chat.user_id == user.id).order_by(db.Chat.updated_at.desc())
    ).all()
    rows = session.scalars(
        select(db.Message).where(db.Message.user_id == user.id).order_by(db.Message.chat_id, db.Message.position)
    ).all()
    by_chat: dict[str, list[dict]] = {}
    for row in rows:
        by_chat.setdefault(row.chat_id, []).append(message_row_json(row))
    articles = session.scalars(
        select(db.FavoriteArticle.article_id).where(db.FavoriteArticle.user_id == user.id).order_by(db.FavoriteArticle.created_at)
    ).all()
    answers = session.scalars(
        select(db.FavoriteAnswer).where(db.FavoriteAnswer.user_id == user.id).order_by(db.FavoriteAnswer.saved_at.desc())
    ).all()
    return {
        "chats": [chat_json(chat, by_chat.get(chat.id, [])) for chat in chats],
        "favoriteArticles": list(articles),
        "favoriteAnswers": [
            {"chatId": a.chat_id, "question": a.question, "message": a.message, "savedAt": iso(a.saved_at)}
            for a in answers
        ],
    }


@router.put("/chats/{chat_id}")
def put_chat(chat_id: ChatIdPath, body: ChatIn, user: db.User = Depends(get_current_user),
             session: Session = Depends(get_db)) -> dict:
    """Создаёт или целиком заменяет чат вместе с сообщениями (идемпотентно)."""
    if body.id is not None and body.id != chat_id:
        raise HTTPException(status_code=422, detail="Идентификатор чата в пути и в теле не совпадает")
    if len({m.id for m in body.messages}) != len(body.messages):
        raise HTTPException(status_code=422, detail="Идентификаторы сообщений повторяются")

    chat = session.get(db.Chat, (user.id, chat_id))
    if chat is None:
        chat = db.Chat(user_id=user.id, id=chat_id)
        session.add(chat)
    chat.title = body.title
    chat.jurisdiction = body.jurisdiction or ""
    chat.created_at = utc(body.createdAt)
    chat.updated_at = utc(body.updatedAt)
    session.flush()

    session.execute(delete(db.Message).where(db.Message.user_id == user.id, db.Message.chat_id == chat_id))
    for position, m in enumerate(body.messages):
        data = message_json(m)
        session.add(db.Message(
            user_id=user.id, chat_id=chat_id, id=m.id, position=position, role=m.role, text=m.text,
            jurisdiction=m.jurisdiction, status=data["status"], error_text=m.errorText,
            reply_status=m.replyStatus, citations=m.citations, created_at=utc(m.createdAt),
        ))
    session.commit()
    return chat_json(chat, load_messages(session, user.id, chat_id))


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: ChatIdPath, user: db.User = Depends(get_current_user),
                session: Session = Depends(get_db)) -> None:
    """Удаляет чат; сообщения удаляются каскадом, избранные ответы остаются."""
    session.execute(delete(db.Chat).where(db.Chat.user_id == user.id, db.Chat.id == chat_id))
    session.commit()


@router.put("/favorites/articles/{article_id}", status_code=204)
def put_favorite_article(article_id: ArticleIdPath, user: db.User = Depends(get_current_user),
                         session: Session = Depends(get_db)) -> None:
    session.merge(db.FavoriteArticle(user_id=user.id, article_id=article_id))
    session.commit()


@router.delete("/favorites/articles/{article_id}", status_code=204)
def delete_favorite_article(article_id: ArticleIdPath, user: db.User = Depends(get_current_user),
                            session: Session = Depends(get_db)) -> None:
    session.execute(delete(db.FavoriteArticle).where(
        db.FavoriteArticle.user_id == user.id, db.FavoriteArticle.article_id == article_id))
    session.commit()


@router.put("/favorites/answers/{message_id}", status_code=204)
def put_favorite_answer(message_id: MessageIdPath, body: FavoriteAnswerIn,
                        user: db.User = Depends(get_current_user), session: Session = Depends(get_db)) -> None:
    if body.message.id != message_id:
        raise HTTPException(status_code=422, detail="Идентификатор сообщения в пути и в теле не совпадает")
    if body.message.role != "assistant":
        raise HTTPException(status_code=422, detail="В избранное можно сохранить только ответ навигатора")
    session.merge(db.FavoriteAnswer(
        user_id=user.id, message_id=message_id, chat_id=body.chatId, question=body.question,
        message=message_json(body.message), saved_at=utc(body.savedAt),
    ))
    session.commit()


@router.delete("/favorites/answers/{message_id}", status_code=204)
def delete_favorite_answer(message_id: MessageIdPath, user: db.User = Depends(get_current_user),
                           session: Session = Depends(get_db)) -> None:
    session.execute(delete(db.FavoriteAnswer).where(
        db.FavoriteAnswer.user_id == user.id, db.FavoriteAnswer.message_id == message_id))
    session.commit()

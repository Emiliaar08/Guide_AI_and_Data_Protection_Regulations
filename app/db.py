"""Подключение к PostgreSQL и модели хранилища: аккаунты, чаты, избранное.

Схема описана в spec/tech/architecture.md (раздел «Аккаунты и рабочее пространство»).
Без переменной DATABASE_URL модуль импортируется, но хранилище считается отключённым.
"""
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chat(Base):
    __tablename__ = "chats"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    jurisdiction: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "chat_id"], ["chats.user_id", "chats.id"], ondelete="CASCADE"),
    )

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FavoriteArticle(Base):
    __tablename__ = "favorite_articles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    article_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FavoriteAnswer(Base):
    __tablename__ = "favorite_answers"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # без внешнего ключа: ответ переживает удаление чата
    question: Mapped[str] = mapped_column(Text)
    message: Mapped[dict] = mapped_column(JSONB)  # копия ответа
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


_session_factory = None


def enabled() -> bool:
    """Хранилище включено, если задан DATABASE_URL."""
    return bool(os.getenv("DATABASE_URL"))


def session_factory():
    """Создаёт подключение при первом обращении, а не при импорте (тесты работают без базы)."""
    global _session_factory
    if _session_factory is None:
        engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
        _session_factory = sessionmaker(engine, expire_on_commit=False)
    return _session_factory

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import db
from app.server import app

needs_storage = pytest.mark.skipif(
    not (db.enabled() and os.getenv("REDIS_URL")),
    reason="нужны DATABASE_URL и REDIS_URL (docker compose up -d)",
)
T0 = "2026-11-26T10:00:00.000Z"
T1 = "2026-11-26T10:00:05.000Z"


def msg(message_id, role, text, **extra):
    return {"id": message_id, "role": role, "text": text, "createdAt": T0, "status": "sent", **extra}


def chat_body(chat_id="c1", messages=None):
    if messages is None:
        messages = [
            msg("m1", "user", "Нужно ли согласие?", jurisdiction="eu"),
            msg("m2", "assistant", "Да. [D13]", replyStatus="ok",
                citations=[{"id": "D13", "doc_title": "GDPR", "article": "ст. 6"}]),
        ]
    return {"id": chat_id, "title": "Согласие", "jurisdiction": "eu", "createdAt": T0, "updatedAt": T1,
            "messages": messages}


@pytest.fixture
def make_user():
    emails = []

    def create():
        email = f"ws-{uuid.uuid4().hex[:8]}@example.com"
        emails.append(email)
        client = TestClient(app)
        response = client.post("/api/auth/register", json={"name": "Тест", "email": email, "password": "password123"})
        assert response.status_code == 201
        return client

    yield create
    if emails:
        with db.session_factory()() as session:
            session.execute(delete(db.User).where(db.User.email.in_(emails)))
            session.commit()


# ---- без базы ----

def test_workspace_disabled_without_storage(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert TestClient(app).get("/api/workspace").status_code == 503


# ---- с настоящими PostgreSQL и Redis ----

@needs_storage
def test_guest_gets_401_everywhere():
    guest = TestClient(app)
    assert guest.get("/api/workspace").status_code == 401
    assert guest.put("/api/chats/c1", json=chat_body()).status_code == 401
    assert guest.delete("/api/chats/c1").status_code == 401
    assert guest.put("/api/favorites/articles/152fz:6").status_code == 401
    assert guest.delete("/api/favorites/answers/m2").status_code == 401


@needs_storage
def test_chat_roundtrip_keeps_order_and_fields(make_user):
    client = make_user()
    response = client.put("/api/chats/c1", json=chat_body())
    assert response.status_code == 200
    workspace = client.get("/api/workspace").json()
    assert [c["id"] for c in workspace["chats"]] == ["c1"]
    chat = workspace["chats"][0]
    assert chat["title"] == "Согласие" and chat["jurisdiction"] == "eu"
    assert chat["createdAt"] == T0 and chat["updatedAt"] == T1
    assert [m["id"] for m in chat["messages"]] == ["m1", "m2"]
    assistant = chat["messages"][1]
    assert assistant["replyStatus"] == "ok" and assistant["citations"][0]["id"] == "D13"
    assert chat["messages"][0]["jurisdiction"] == "eu"


@needs_storage
def test_put_replaces_messages_and_is_idempotent(make_user):
    client = make_user()
    client.put("/api/chats/c1", json=chat_body())
    client.put("/api/chats/c1", json=chat_body())
    only_one = chat_body(messages=[msg("m1", "user", "Только один вопрос")])
    assert client.put("/api/chats/c1", json=only_one).status_code == 200
    chat = client.get("/api/workspace").json()["chats"][0]
    assert [m["id"] for m in chat["messages"]] == ["m1"]
    assert chat["messages"][0]["text"] == "Только один вопрос"


@needs_storage
def test_pending_message_is_saved_as_interrupted(make_user):
    client = make_user()
    body = chat_body(messages=[msg("m1", "user", "Вопрос", status="pending")])
    client.put("/api/chats/c1", json=body)
    assert client.get("/api/workspace").json()["chats"][0]["messages"][0]["status"] == "interrupted"


@needs_storage
def test_users_do_not_see_each_others_data(make_user):
    alice, bob = make_user(), make_user()
    alice.put("/api/chats/c1", json=chat_body())
    alice.put("/api/favorites/articles/152fz:6")
    assert bob.get("/api/workspace").json() == {"chats": [], "favoriteArticles": [], "favoriteAnswers": []}
    # тот же идентификатор у другого пользователя — отдельный чат
    bob.put("/api/chats/c1", json=chat_body(messages=[msg("m1", "user", "Чужой чат")]))
    assert len(alice.get("/api/workspace").json()["chats"][0]["messages"]) == 2
    assert bob.delete("/api/chats/c1").status_code == 204
    assert len(alice.get("/api/workspace").json()["chats"]) == 1


@needs_storage
def test_delete_chat_keeps_favorite_answer(make_user):
    client = make_user()
    client.put("/api/chats/c1", json=chat_body())
    answer = msg("m2", "assistant", "Да. [D13]", replyStatus="ok", citations=[{"id": "D13"}])
    favorite = {"chatId": "c1", "question": "Нужно ли согласие?", "savedAt": T1, "message": answer}
    assert client.put("/api/favorites/answers/m2", json=favorite).status_code == 204
    assert client.delete("/api/chats/c1").status_code == 204
    assert client.delete("/api/chats/c1").status_code == 204  # повторное удаление не ошибка
    workspace = client.get("/api/workspace").json()
    assert workspace["chats"] == []
    saved = workspace["favoriteAnswers"][0]
    assert saved["chatId"] == "c1" and saved["question"] == "Нужно ли согласие?"
    assert saved["message"]["text"] == "Да. [D13]" and saved["savedAt"] == T1


@needs_storage
def test_favorite_articles(make_user):
    client = make_user()
    assert client.put("/api/favorites/articles/152fz:6").status_code == 204
    assert client.put("/api/favorites/articles/152fz:6").status_code == 204  # повтор не создаёт дубликат
    client.put("/api/favorites/articles/gdpr:28")
    assert sorted(client.get("/api/workspace").json()["favoriteArticles"]) == ["152fz:6", "gdpr:28"]
    assert client.delete("/api/favorites/articles/152fz:6").status_code == 204
    assert client.get("/api/workspace").json()["favoriteArticles"] == ["gdpr:28"]
    assert client.put("/api/favorites/articles/bad id!").status_code == 422


@needs_storage
def test_favorite_answer_validation(make_user):
    client = make_user()
    answer = msg("m2", "assistant", "Ответ")
    body = {"chatId": None, "question": "Вопрос", "savedAt": T1, "message": answer}
    assert client.put("/api/favorites/answers/other-id", json=body).status_code == 422
    user_message = {**body, "message": msg("m2", "user", "Вопрос")}
    assert client.put("/api/favorites/answers/m2", json=user_message).status_code == 422
    assert client.put("/api/favorites/answers/m2", json=body).status_code == 204
    assert client.delete("/api/favorites/answers/m2").status_code == 204
    assert client.get("/api/workspace").json()["favoriteAnswers"] == []


@needs_storage
def test_chat_validation(make_user):
    client = make_user()
    assert client.put("/api/chats/c1", json=chat_body(chat_id="другой")).status_code == 422  # id в теле не совпадает
    assert client.put("/api/chats/bad id!", json=chat_body()).status_code == 422
    duplicates = chat_body(messages=[msg("m1", "user", "а"), msg("m1", "user", "б")])
    assert client.put("/api/chats/c1", json=duplicates).status_code == 422
    too_many = chat_body(messages=[msg(f"m{i}", "user", "т") for i in range(201)])
    assert client.put("/api/chats/c1", json=too_many).status_code == 422
    assert client.get("/api/workspace").json()["chats"] == []

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import accounts, db
from app.server import app

needs_storage = pytest.mark.skipif(
    not (db.enabled() and os.getenv("REDIS_URL")),
    reason="нужны DATABASE_URL и REDIS_URL (docker compose up -d)",
)


# ---- без базы ----

def test_password_hash_roundtrip():
    stored = accounts.hash_password("correct horse")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert accounts.verify_password("correct horse", stored)
    assert not accounts.verify_password("wrong", stored)


def test_password_hash_is_salted():
    assert accounts.hash_password("same") != accounts.hash_password("same")


def test_broken_hash_does_not_verify():
    assert not accounts.verify_password("x", "not-a-hash")


def test_accounts_disabled_without_storage(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    client = TestClient(app)
    for method, path in [("GET", "/api/auth/me"), ("POST", "/api/auth/logout"),
                         ("POST", "/api/auth/login"), ("POST", "/api/auth/register")]:
        assert client.request(method, path, json={}).status_code == 503


# ---- с настоящими PostgreSQL и Redis ----

@pytest.fixture
def client():
    return TestClient(app)  # у каждого теста свои cookie


@pytest.fixture
def email():
    value = f"test-{uuid.uuid4().hex[:8]}@example.com"
    yield value
    with db.session_factory()() as session:
        session.execute(delete(db.User).where(db.User.email == value))
        session.commit()


def register(client, email, password="password123", name="Тест"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


@needs_storage
def test_register_logs_in(client, email):
    r = register(client, email)
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["email"] == email and user["name"] == "Тест" and user["id"]
    assert "password" not in r.text
    assert "httponly" in r.headers["set-cookie"].lower()
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"] == user


@needs_storage
def test_duplicate_email_is_conflict_even_in_other_case(client, email):
    assert register(client, email).status_code == 201
    assert register(TestClient(app), email.upper()).status_code == 409


@needs_storage
def test_invalid_registration_fields(client, email):
    assert register(client, email, password="short").status_code == 422
    assert register(client, "not-an-email").status_code == 422
    assert register(client, email, name="   ").status_code == 422


@needs_storage
def test_login_and_wrong_credentials(client, email):
    register(client, email)
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"}).status_code == 401
    ok = fresh.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert ok.status_code == 200 and fresh.get("/api/auth/me").status_code == 200


@needs_storage
def test_me_requires_valid_session(client):
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("session_id", "fake-token")
    assert client.get("/api/auth/me").status_code == 401


@needs_storage
def test_logout_ends_session(client, email):
    register(client, email)
    token = client.cookies.get("session_id")
    assert client.post("/api/auth/logout").status_code == 204
    other = TestClient(app)
    other.cookies.set("session_id", token)  # старый токен больше не действует
    assert other.get("/api/auth/me").status_code == 401

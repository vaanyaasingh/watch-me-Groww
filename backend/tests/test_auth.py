"""Real Firebase Auth (app/auth.py): token verification is mocked here
(no real ID token or network call in a unit test) — what's actually under
test is get_current_user_id's own logic: rejecting missing/invalid
tokens, and resolving a verified token to the right app User row,
creating one on a person's first-ever authenticated call.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.auth as auth_module
from app.db import Base
from app.models import User


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(auth_module, "SessionLocal", TestSession)
    monkeypatch.setattr(auth_module, "FIREBASE_PROJECT_ID", "test-project")
    return TestSession


def test_missing_authorization_header_is_rejected(session_factory):
    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user_id(authorization=None)
    assert exc_info.value.status_code == 401


def test_non_bearer_header_is_rejected(session_factory):
    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user_id(authorization="Basic abc123")
    assert exc_info.value.status_code == 401


def test_invalid_token_is_rejected(monkeypatch, session_factory):
    def fake_verify(token, request, audience):
        raise ValueError("Token expired")

    monkeypatch.setattr(auth_module.google_id_token, "verify_firebase_token", fake_verify)

    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user_id(authorization="Bearer bad-token")
    assert exc_info.value.status_code == 401


def test_valid_token_creates_a_new_user_on_first_call(monkeypatch, session_factory):
    monkeypatch.setattr(
        auth_module.google_id_token,
        "verify_firebase_token",
        lambda token, request, audience: {"uid": "firebase-uid-1", "email": "new@example.com"},
    )

    user_id = auth_module.get_current_user_id(authorization="Bearer good-token")

    session = session_factory()
    user = session.query(User).filter_by(firebase_uid="firebase-uid-1").first()
    session.close()
    assert user is not None
    assert user.id == user_id
    assert user.email == "new@example.com"


def test_insert_race_recovers_instead_of_raising(monkeypatch, session_factory):
    """Directly exercises the except IntegrityError branch: a session
    whose own .first() query found nothing (so it proceeds to INSERT), but
    another request's row for the same firebase_uid lands first — the
    commit must hit the UNIQUE constraint and _resolve_or_create_user must
    recover by reading that row back rather than propagating the error."""
    concurrent_session = session_factory()
    session = session_factory()

    real_commit = session.commit

    def commit_after_concurrent_insert_wins():
        concurrent_session.add(User(firebase_uid="firebase-uid-race-2", email="other@example.com"))
        concurrent_session.commit()
        real_commit()

    monkeypatch.setattr(session, "commit", commit_after_concurrent_insert_wins)

    resolved = auth_module._resolve_or_create_user(session, "firebase-uid-race-2", "race@example.com")
    session.close()
    concurrent_session.close()

    verify_session = session_factory()
    matches = verify_session.query(User).filter_by(firebase_uid="firebase-uid-race-2").all()
    verify_session.close()
    assert len(matches) == 1
    assert resolved.id == matches[0].id
    assert resolved.email == "other@example.com"  # the row that actually won the race, not this call's own data


def test_valid_token_resolves_the_same_user_on_a_later_call(monkeypatch, session_factory):
    monkeypatch.setattr(
        auth_module.google_id_token,
        "verify_firebase_token",
        lambda token, request, audience: {"uid": "firebase-uid-2", "email": "again@example.com"},
    )

    first_id = auth_module.get_current_user_id(authorization="Bearer token-1")
    second_id = auth_module.get_current_user_id(authorization="Bearer token-2")

    assert first_id == second_id
    session = session_factory()
    matches = session.query(User).filter_by(firebase_uid="firebase-uid-2").all()
    session.close()
    assert len(matches) == 1  # no duplicate row created on the second call

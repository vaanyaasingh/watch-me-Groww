"""Real Firebase Authentication (docs/plan.md §4 — no longer deferred now
that the GCP billing block is resolved). Every route that reads/writes a
specific person's data depends on get_current_user_id instead of the old
hardcoded app.seed.DEMO_USER_ID.

Verifies the ID token the frontend attaches as `Authorization: Bearer
<token>` (frontend/lib/api.ts) using google-auth's
verify_firebase_token — this only needs Firebase's public certs (fetched
over HTTPS, cached by the library) and the project id, not a service
account key or Application Default Credentials. That matters because this
backend runs on Render, not GCP, so it has no ADC available the way the
Vertex AI calls do locally/on Cloud Run.
"""

import os

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User

# Same project as GOOGLE_CLOUD_PROJECT (Vertex AI) — a Firebase project is
# just a GCP project with Firebase enabled, one id for both.
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")

# Reused across requests — this is what caches Google's public signing
# certs instead of re-fetching them on every single call.
_google_request = google_auth_requests.Request()


def _resolve_or_create_user(session: Session, firebase_uid: str, email: str | None) -> User:
    user = session.query(User).filter_by(firebase_uid=firebase_uid).first()
    if user is not None:
        return user
    user = User(firebase_uid=firebase_uid, email=email or f"{firebase_uid}@firebase.local")
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # A person's first sign-in fires several API calls in parallel
        # (watchlist, attention-feed, /me, ...), each hitting this same
        # "no row yet" branch — whichever request's INSERT loses the race
        # hits User.firebase_uid's UNIQUE constraint here rather than
        # crashing the request: the other request already created the row,
        # so just read it back instead of treating this as a real error.
        session.rollback()
        user = session.query(User).filter_by(firebase_uid=firebase_uid).first()
        if user is None:
            raise
        return user
    session.refresh(user)
    return user


def get_current_user_id(authorization: str | None = Header(default=None)) -> int:
    """FastAPI dependency: verifies the bearer token and returns the app's
    own User.id (creating the row on a person's first authenticated call —
    there's no separate signup endpoint on this backend, Firebase already
    owns account creation on the frontend)."""
    if not FIREBASE_PROJECT_ID:
        raise HTTPException(status_code=500, detail="Server misconfigured: FIREBASE_PROJECT_ID/GOOGLE_CLOUD_PROJECT not set")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        claims = google_id_token.verify_firebase_token(token, _google_request, audience=FIREBASE_PROJECT_ID)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid token: not a Firebase ID token")

    firebase_uid = claims.get("uid") or claims.get("sub")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    session = SessionLocal()
    try:
        user = _resolve_or_create_user(session, firebase_uid, claims.get("email"))
        return user.id
    finally:
        session.close()

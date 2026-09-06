import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.db import SessionLocal
from app.seed import seed_demo_data

app = FastAPI(
    title="Smart Market Watchlist API",
    description="Change-detection and attention-ranking layer over a watchlist.",
)

# Next.js dev server origin always allowed; ALLOWED_ORIGINS (comma-separated)
# adds the deployed frontend's origin (e.g. the Vercel URL) in production —
# set once that URL is known, without needing a code change to add it.
_extra_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", *_extra_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def _seed_on_startup() -> None:
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

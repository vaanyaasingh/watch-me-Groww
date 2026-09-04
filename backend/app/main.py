from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.db import SessionLocal
from app.seed import seed_demo_data

app = FastAPI(
    title="Smart Market Watchlist API",
    description="Change-detection and attention-ranking layer over a watchlist.",
)

# Next.js dev server origin only — this is a hackathon demo, not a
# multi-tenant public API, so a permissive allowlist is simplest and
# sufficient rather than building out real per-origin config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

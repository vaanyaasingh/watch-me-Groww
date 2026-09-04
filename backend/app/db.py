"""SQLAlchemy engine/session setup.

No models live here yet (Phase 2 defines the data model in docs/plan.md §5).
This just gives Alembic a `Base.metadata` to target and the app a session
factory to depend on later. Defaults to a local SQLite file so the backend
is runnable with zero setup; set DATABASE_URL to point at Postgres.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

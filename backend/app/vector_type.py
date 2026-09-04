"""EmbeddingType — stores a NewsItem's embedding as a native pgvector column
on Postgres (docs/plan.md §4 commits to "Cloud SQL Postgres with pgvector,
one database for relational + vector data"), and as a JSON-encoded float
list on SQLite.

SQLite has no vector type at all, and this project's default/test database
is SQLite (see app/db.py — zero-setup local dev). Without this bridge,
NewsItem simply couldn't be defined in a way that works against both
databases, and the whole test suite would need a real Postgres instance
just to import app.models.
"""

from sqlalchemy import JSON, TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pgvector is an optional dependency for non-Postgres setups
    Vector = None

EMBEDDING_DIM = 768  # kept in sync with app/embeddings.py's EMBEDDING_DIM


class EmbeddingType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return list(value)

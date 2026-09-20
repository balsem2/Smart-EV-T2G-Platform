from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class shared by all SQLAlchemy models."""


@lru_cache
def get_engine() -> Engine:
    """Create one reusable SQLAlchemy engine for the configured database."""
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Copy backend/.env.example to backend/.env "
            "and add your local PostgreSQL credentials."
        )

    return create_engine(settings.database_url, pool_pre_ping=True)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per API request and close it afterwards."""
    session_factory = sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )
    database_session = session_factory()
    try:
        yield database_session
    finally:
        database_session.close()


def ping_database() -> None:
    """Run a minimal query to verify that PostgreSQL is reachable."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))

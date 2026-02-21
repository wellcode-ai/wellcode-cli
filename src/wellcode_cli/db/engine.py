"""Database engine factory supporting SQLite (default) and PostgreSQL."""

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_config_value

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None

DATA_DIR = Path.home() / ".wellcode" / "data"


def _sqlite_wal_mode(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_database_url() -> str:
    url = get_config_value("DATABASE_URL")
    if url:
        return url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATA_DIR / 'wellcode.db'}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_database_url()
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20
            kwargs["pool_pre_ping"] = True

        _engine = create_engine(url, echo=False, **kwargs)

        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _sqlite_wal_mode)

    return _engine


def get_session() -> Session:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory()


def init_db():
    """Create all tables. For production use Alembic migrations instead."""
    from .models import Base
    Base.metadata.create_all(get_engine())

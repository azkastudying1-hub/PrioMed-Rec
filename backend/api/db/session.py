"""
api/db/session.py
------------------
SQLAlchemy engine, session factory, dan dependency FastAPI.

Mendukung SQLite (demo) dan PostgreSQL (pilot) via DATABASE_URL env var.
SQLite menggunakan WAL mode untuk konkurensi yang lebih baik.

Env vars:
  DATABASE_URL    — SQLAlchemy URL (default: sqlite:///data/priomed.db)
                    Contoh PostgreSQL: postgresql+psycopg2://user:pass@host:5432/priomed
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "priomed.db")
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

_is_sqlite = DATABASE_URL.startswith("sqlite")

# Buat direktori data jika belum ada (untuk SQLite)
if _is_sqlite:
    _db_file = DATABASE_URL.replace("sqlite:///", "")
    Path(_db_file).parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    # SQLite: perbolehkan multi-thread dengan check_same_thread=False dan timeout 30s
    connect_args={"check_same_thread": False, "timeout": 30.0} if _is_sqlite else {},
    # PostgreSQL: connection pool settings
    pool_pre_ping=True,
)

# Aktifkan WAL mode, foreign keys, dan busy_timeout untuk SQLite
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Base class untuk semua SQLAlchemy model."""
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a SQLAlchemy session and closes it after request.

    Usage:
        @router.get("/endpoint")
        def endpoint(db: Session = Depends(get_session)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Context manager for non-FastAPI code (scripts, services, tests)
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def session_scope():
    """
    Context manager for use in scripts, services, and tests (not in FastAPI request handlers).

    Usage:
        with session_scope() as session:
            session.add(obj)
            session.commit()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

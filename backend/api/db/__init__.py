"""
api/db/__init__.py
------------------
SQLAlchemy database package untuk PrioMed-Rec.

Menyediakan:
  - engine + session factory
  - Base declarative model
  - get_session() dependency untuk FastAPI
"""

from api.db.session import engine, SessionLocal, Base, get_session

__all__ = ["engine", "SessionLocal", "Base", "get_session"]

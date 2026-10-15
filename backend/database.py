"""Database setup: SQLAlchemy engine, sessions, and table creation.

DATABASE_URL env var selects the backend. Defaults to a local SQLite file
so the app runs with zero setup; point it at SQL Server for the real DB:

    mssql+pyodbc://sa:<password>@localhost:1433/social_analyzer?driver=ODBC+Driver+18+for+SQL+Server
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./analyzer.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import models  # noqa: F401  (registers models with Base)

    Base.metadata.create_all(bind=engine)

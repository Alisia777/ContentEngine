from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()


def _ensure_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "script_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("script_jobs")}
    migrations = {
        "llm_provider": "ALTER TABLE script_jobs ADD COLUMN llm_provider VARCHAR(120)",
        "llm_model": "ALTER TABLE script_jobs ADD COLUMN llm_model VARCHAR(160)",
        "llm_request_json": "ALTER TABLE script_jobs ADD COLUMN llm_request_json TEXT DEFAULT '{}'",
        "llm_response_json": "ALTER TABLE script_jobs ADD COLUMN llm_response_json TEXT DEFAULT '{}'",
    }
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))

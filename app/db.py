from collections.abc import Iterator
from sqlite3 import Connection as SqliteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {"connect_timeout": 5}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    if isinstance(dbapi_connection, SqliteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


DbSessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = DbSessionFactory()
    try:
        yield db
    finally:
        db.close()

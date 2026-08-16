from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.config import settings


# ============================================================
# DATABASE URL NORMALIZATION
# ============================================================

def _normalize_database_url(
    database_url: str,
) -> str:

    url = database_url.strip()


    if url.startswith(
        "postgres://"
    ):

        return url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1,
        )


    if url.startswith(
        "postgresql://"
    ):

        return url.replace(
            "postgresql://",
            "postgresql+psycopg2://",
            1,
        )


    return url


DATABASE_URL = (
    _normalize_database_url(
        settings.database_url
    )
)


# ============================================================
# SQLALCHEMY ENGINE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ============================================================
# FASTAPI DB DEPENDENCY
# ============================================================

def get_db() -> Generator[
    Session,
    None,
    None,
]:

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()
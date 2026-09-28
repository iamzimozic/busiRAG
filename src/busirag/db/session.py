import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def normalize_database_url(url: str) -> str:
    """
    Use the psycopg 3 driver for plain postgres URLs.

    Managed Postgres providers hand out postgres:// or postgresql://
    URLs, which SQLAlchemy would map to psycopg2 (not installed).
    """

    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]

    return url


DATABASE_URL = normalize_database_url(os.environ["DATABASE_URL"])

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
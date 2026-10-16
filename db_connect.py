import os
import sys
from functools import lru_cache

from dotenv import dotenv_values, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()

try:
    import psycopg2  # noqa: F401
    DRIVER = "postgresql+psycopg2"
except ImportError:
    DRIVER = "postgresql+psycopg"


def _first_env(*names):
    for n in names:
        if os.getenv(n):
            return os.getenv(n)
    return None


@lru_cache(maxsize=1)
def get_engine():
    url = os.getenv("DATABASE_URL")
    if url:
        for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://",
                       "postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = DRIVER + "://" + url[len(prefix):]
                break
        return create_engine(url)

    name = _first_env("DB_NAME", "POSTGRES_DB")
    user = _first_env("DB_USER", "POSTGRES_USER")
    password = _first_env("DB_PASSWORD", "POSTGRES_PASSWORD")
    host = _first_env("DB_HOST", "POSTGRES_HOST") or "localhost"
    port = _first_env("DB_PORT", "POSTGRES_PORT") or "5432"

    if not (name and user and password):
        print("Could not find database settings in .env")
        print("Variable names found:", list(dotenv_values().keys()))
        sys.exit("Add DB_NAME, DB_USER, DB_PASSWORD to .env")

    return create_engine(URL.create(
        drivername=DRIVER, username=user, password=password,
        host=host, port=int(port), database=name))

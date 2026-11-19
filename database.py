
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), ".env"),
    override=True,
)


def _first_env(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _connect():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        for prefix in (
            "postgresql+psycopg2://",
            "postgresql+psycopg://",
        ):
            if database_url.startswith(prefix):
                database_url = (
                    "postgresql://" + database_url[len(prefix):]
                )
                break

        return psycopg2.connect(
            database_url,
            connect_timeout=5,
        )

    db_name = _first_env("DB_NAME", "POSTGRES_DB")
    db_user = _first_env("DB_USER", "POSTGRES_USER")
    db_password = _first_env("DB_PASSWORD", "POSTGRES_PASSWORD")
    db_host = _first_env("DB_HOST", "POSTGRES_HOST") or "localhost"
    db_port = _first_env("DB_PORT", "POSTGRES_PORT") or "5432"

    if not all((db_name, db_user, db_password)):
        raise RuntimeError(
            "Missing PostgreSQL settings. Check DB_NAME, DB_USER, "
            "DB_PASSWORD or their POSTGRES_* equivalents in .env."
        )

    return psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=int(db_port),
        connect_timeout=5,
    )


class DatabaseManager:

    @staticmethod
    def get_db_type():
        # Never silently fall back to an old SQLite database.
        conn = _connect()
        conn.close()
        return "postgresql"

    @classmethod
    def execute_query(cls, sql_query, params=()):
        conn = _connect()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql_query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

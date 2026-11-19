import json

from sqlalchemy import text

from db_connect import get_engine

AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS ai_audit_log (
    id          SERIAL PRIMARY KEY,
    asked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    question    TEXT NOT NULL,
    model       TEXT,
    tool_calls  JSONB,
    answer      TEXT,
    latency_ms  INTEGER,
    status      TEXT NOT NULL
)
"""


def ensure_audit_table():
    with get_engine().begin() as conn:
        conn.execute(text(AUDIT_SQL))


def log_interaction(question, model, tool_log, answer, latency_ms, status):
    try:
        ensure_audit_table()
        with get_engine().begin() as conn:
            conn.execute(
                text("""INSERT INTO ai_audit_log
                        (question, model, tool_calls, answer, latency_ms, status)
                        VALUES (:q, :m, CAST(:t AS JSONB), :a, :l, :s)"""),
                {"q": question, "m": model, "t": json.dumps(tool_log, default=str),
                 "a": answer, "l": latency_ms, "s": status})
    except Exception as exc:
        print(f"[warning] could not write audit log: {exc!r}")

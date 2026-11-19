import os
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

try:
    import psycopg2  # noqa: F401
    DRIVER = "postgresql+psycopg2"
except ImportError:
    DRIVER = "postgresql+psycopg"

# ============================================================
# 1. SETTINGS
# ============================================================

BASE = Path("data/processed")
SOURCES = {
    "annual": BASE / "apple_financial_data_annual.csv",
    "quarterly": BASE / "apple_financial_data_quarterly.csv",
    "snapshots": BASE / "apple_balance_sheet_snapshots.csv",
}
TABLE = "financial_facts_clean"

COLUMNS = [
    "company_name", "cik", "metric", "sec_concept", "period_start",
    "period_end", "duration_days", "fiscal_year", "fiscal_period", "value",
    "unit", "form", "filing_date", "accession_number", "frame",
    "record_type", "is_derived",
]
KEY_COLS = ["metric", "period_start", "period_end", "fiscal_year",
            "fiscal_period", "accession_number"]
STRONG_KEY = ["cik", "metric", "sec_concept", "period_start", "period_end",
              "fiscal_year", "fiscal_period", "accession_number", "unit",
              "record_type"]
TEXT_COLS = ["company_name", "sec_concept", "metric", "fiscal_period", "unit",
             "form", "accession_number", "frame", "record_type"]
DATE_COLS = ["period_start", "period_end", "filing_date"]

EXPECTED_TOTAL = 743
EXPECTED_REVENUE = {
    "2020-09-26": 274515000000,
    "2021-09-25": 365817000000,
    "2022-09-24": 394328000000,
    "2023-09-30": 383285000000,
    "2024-09-28": 391035000000,
    "2025-09-27": 416161000000,
}

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id               SERIAL PRIMARY KEY,
    company_name     TEXT,
    cik              BIGINT NOT NULL,
    metric           TEXT NOT NULL,
    sec_concept      TEXT,
    period_start     DATE,
    period_end       DATE NOT NULL,
    duration_days    INTEGER,
    fiscal_year      INTEGER,
    fiscal_period    TEXT,
    value            NUMERIC(24, 2) NOT NULL,
    unit             TEXT,
    form             TEXT,
    filing_date      DATE,
    accession_number TEXT,
    frame            TEXT,
    record_type      TEXT NOT NULL
        CHECK (record_type IN ('annual_flow', 'quarter_flow', 'balance_snapshot')),
    is_derived       BOOLEAN NOT NULL DEFAULT FALSE,
    source_file      TEXT NOT NULL,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fin_clean_key UNIQUE NULLS NOT DISTINCT
        (cik, metric, sec_concept, period_start, period_end,
         fiscal_year, fiscal_period, accession_number, unit, record_type)
);
"""
INDEX_SQL = [
    f"CREATE INDEX IF NOT EXISTS idx_ffc_metric_period ON {TABLE} (metric, period_end);",
    f"CREATE INDEX IF NOT EXISTS idx_ffc_type_year ON {TABLE} (record_type, fiscal_year);",
]

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f"  ->  {detail}" if detail else ""))


def header(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


# ============================================================
# 2. DATABASE CONNECTION
# ============================================================

def first_env(*names):
    for n in names:
        if os.getenv(n):
            return os.getenv(n)
    return None


def build_engine():
    url = os.getenv("DATABASE_URL")
    if url:
        for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://",
                       "postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = DRIVER + "://" + url[len(prefix):]
                break
        return create_engine(url)

    name = first_env("DB_NAME", "POSTGRES_DB")
    user = first_env("DB_USER", "POSTGRES_USER")
    password = first_env("DB_PASSWORD", "POSTGRES_PASSWORD")
    host = first_env("DB_HOST", "POSTGRES_HOST") or "localhost"
    port = first_env("DB_PORT", "POSTGRES_PORT") or "5432"

    if not (name and user and password):
        print("Could not find database settings in your .env file.")
        print("Variable names found in .env (names only):",
              list(dotenv_values().keys()))
        sys.exit("Add DB_NAME, DB_USER, DB_PASSWORD (and DB_HOST, DB_PORT) to .env")

    return create_engine(URL.create(
        drivername=DRIVER, username=user, password=password,
        host=host, port=int(port), database=name))


# ============================================================
# 3. READ AND VALIDATE THE CSV FILES (before touching the DB)
# ============================================================

def read_sources():
    data = {}
    for name, path in SOURCES.items():
        if not path.exists():
            sys.exit(f"Missing file: {path}")
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = [c for c in COLUMNS if c not in df.columns]
        if missing:
            sys.exit(f"{path} is missing columns: {missing}")
        data[name] = df[COLUMNS].copy()
    return data


def key_set(df):
    return set(map(tuple, df[KEY_COLS].values.tolist()))


def build_canonical(data):
    annual = data["annual"]
    flows = annual[annual["record_type"] == "annual_flow"].copy()
    flows["source_file"] = "annual"
    quarterly = data["quarterly"].copy()
    quarterly["source_file"] = "quarterly"
    snaps = data["snapshots"].copy()
    snaps["source_file"] = "snapshots"
    annual_balance = annual[annual["record_type"] == "balance_snapshot"]
    return pd.concat([flows, quarterly, snaps], ignore_index=True), annual_balance, snaps


def validate_csv(canon, annual_balance, snaps):
    header("CHECK GROUP A: CSV VALIDATION (nothing written yet)")

    check("Canonical row count is 743", len(canon) == EXPECTED_TOTAL, f"{len(canon)} rows")
    check("Annual balance rows all exist in snapshot file",
          key_set(annual_balance) <= key_set(snaps),
          f"{len(annual_balance)} rows compared")

    values = pd.to_numeric(canon["value"], errors="coerce")
    check("Every value is numeric", values.notna().all())

    for col in DATE_COLS:
        nonblank = canon[col].str.strip() != ""
        parsed = pd.to_datetime(canon[col], errors="coerce")
        bad = int((nonblank & parsed.isna()).sum())
        check(f"All non-blank {col} values are valid dates", bad == 0, f"{bad} bad")

    check("period_end never blank", (canon["period_end"].str.strip() != "").all())
    check("Only one company (single CIK)", canon["cik"].nunique() == 1,
          str(sorted(canon["cik"].unique())))
    check("Only allowed record types",
          set(canon["record_type"]) <= {"annual_flow", "quarter_flow", "balance_snapshot"})
    check("No duplicate rows on the full record key",
          int(canon.duplicated(subset=STRONG_KEY).sum()) == 0)

    if not all(RESULTS):
        sys.exit("\nCSV validation failed. Database was NOT touched. Send me this output.")


def to_typed(df):
    out = pd.DataFrame(index=df.index)
    for col in TEXT_COLS:
        out[col] = df[col].where(df[col].str.strip() != "", None)
    out["cik"] = pd.to_numeric(df["cik"]).astype("Int64")
    out["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype("Int64")
    out["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce").round().astype("Int64")
    for col in DATE_COLS:
        out[col] = pd.to_datetime(df[col], errors="coerce")
    out["value"] = df["value"].str.strip().map(Decimal)
    out["is_derived"] = df["is_derived"].str.strip().str.lower().eq("true")
    out["source_file"] = df["source_file"]
    return out


# ============================================================
# 4. LOAD INTO POSTGRESQL (one transaction)
# ============================================================

def load(engine, typed):
    header("LOADING INTO POSTGRESQL")
    with engine.begin() as conn:
        conn.execute(text(CREATE_SQL))
        for stmt in INDEX_SQL:
            conn.execute(text(stmt))
        conn.execute(text(f"TRUNCATE TABLE {TABLE} RESTART IDENTITY"))
        typed.to_sql(TABLE, conn, if_exists="append", index=False,
                     method="multi", chunksize=500)
        n = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        if n != len(typed):
            raise RuntimeError(f"Sent {len(typed)} rows but table has {n}. Rolled back.")
    print(f"Loaded {n} rows into '{TABLE}' (transaction committed).")


# ============================================================
# 5. VERIFY THE DATABASE AGAINST THE CSV FILES
# ============================================================

def verify(engine, typed):
    header("CHECK GROUP B: DATABASE vs CSV")
    with engine.connect() as conn:
        def scalar(sql):
            return conn.execute(text(sql)).scalar()

        total = scalar(f"SELECT COUNT(*) FROM {TABLE}")
        check("Total rows in database = 743", total == EXPECTED_TOTAL, f"{total}")

        exp_counts = typed["record_type"].value_counts().to_dict()
        db_counts = dict(conn.execute(text(
            f"SELECT record_type, COUNT(*) FROM {TABLE} GROUP BY record_type")).all())
        check("Row counts per record_type match CSV", exp_counts == db_counts,
              f"db={db_counts}")

        exp_sums = {}
        for rt, val in zip(typed["record_type"], typed["value"]):
            exp_sums[rt] = exp_sums.get(rt, Decimal(0)) + val
        db_sums = dict(conn.execute(text(
            f"SELECT record_type, SUM(value) FROM {TABLE} GROUP BY record_type")).all())
        check("Sum of values per record_type matches CSV exactly",
              all(db_sums.get(k) == v for k, v in exp_sums.items()))

        nulls = scalar(f"""SELECT COUNT(*) FROM {TABLE}
                           WHERE metric IS NULL OR period_end IS NULL
                              OR value IS NULL OR record_type IS NULL""")
        check("No NULLs in metric / period_end / value / record_type", nulls == 0)

        dups = scalar(f"""SELECT COUNT(*) FROM (
                              SELECT 1 FROM {TABLE}
                              GROUP BY cik, metric, sec_concept, period_start, period_end,
                                       fiscal_year, fiscal_period, accession_number,
                                       unit, record_type
                              HAVING COUNT(*) > 1) d""")
        check("No duplicate records in database", dups == 0)

        bad_start = scalar(f"""SELECT COUNT(*) FROM {TABLE}
              WHERE (record_type = 'balance_snapshot' AND period_start IS NOT NULL)
                 OR (record_type <> 'balance_snapshot' AND period_start IS NULL)""")
        check("period_start blank only for balance snapshots", bad_start == 0)

        bad_annual = scalar(f"""SELECT COUNT(*) FROM {TABLE}
              WHERE record_type = 'annual_flow'
                AND (duration_days IS NULL OR duration_days NOT BETWEEN 350 AND 380)""")
        check("Annual rows span about one year (350-380 days)", bad_annual == 0,
              f"{bad_annual} outside range")

        bad_q = scalar(f"""SELECT COUNT(*) FROM {TABLE}
              WHERE record_type = 'quarter_flow'
                AND (duration_days IS NULL OR duration_days NOT BETWEEN 80 AND 105)""")
        check("Quarterly rows span about one quarter (80-105 days)", bad_q == 0,
              f"{bad_q} outside range")

        conflicts = scalar(f"""SELECT COUNT(*) FROM (
                SELECT 1 FROM {TABLE}
                GROUP BY record_type, metric, period_end
                HAVING COUNT(DISTINCT value) > 1) c""")
        check("No period has two different values for the same metric", conflicts == 0,
              f"{conflicts} conflicting periods")

        rev = {}
        for pe, val in conn.execute(text(f"""
                SELECT period_end::text, value FROM {TABLE}
                WHERE metric = 'revenue' AND record_type = 'annual_flow'""")).all():
            rev.setdefault(pe, set()).add(int(val))
        for pe, expected in EXPECTED_REVENUE.items():
            got = rev.get(pe)
            if not got:
                check(f"Revenue {pe}", False, "no annual revenue row found")
            else:
                check(f"Revenue {pe} = {expected:,}", got == {expected}, f"found {sorted(got)}")

        header("INFO: DATA COVERAGE")
        print(pd.read_sql(text(f"""
            SELECT record_type, metric, COUNT(*) AS records,
                   MIN(period_end) AS earliest, MAX(period_end) AS latest
            FROM {TABLE} GROUP BY record_type, metric
            ORDER BY record_type, metric"""), conn).to_string(index=False))

        header("INFO: ANNUAL REVENUE IN DATABASE")
        print(pd.read_sql(text(f"""
            SELECT period_end, value, fiscal_year, fiscal_period, form, accession_number
            FROM {TABLE}
            WHERE metric = 'revenue' AND record_type = 'annual_flow'
            ORDER BY period_end"""), conn).to_string(index=False))

    header("INFO: OLD TABLES (must be untouched: expect 1 / 1808 / 17)")
    for t in ["companies", "financial_facts", "annual_kpis"]:
        try:
            with engine.connect() as conn:
                print(f"{t}: {conn.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar()} rows")
        except Exception as exc:
            print(f"{t}: could not read ({type(exc).__name__})")


# ============================================================
# 6. MAIN
# ============================================================

def main():
    data = read_sources()
    canon, annual_balance, snaps = build_canonical(data)
    validate_csv(canon, annual_balance, snaps)
    typed = to_typed(canon)

    engine = build_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        sys.exit(f"Cannot connect to PostgreSQL: {exc}")

    load(engine, typed)
    verify(engine, typed)

    header("FINAL RESULT")
    print(f"{sum(RESULTS)} of {len(RESULTS)} checks passed")
    if all(RESULTS):
        print("ALL CHECKS PASSED. The database is ready for KPI generation.")
    else:
        print("Some checks FAILED. Do not build KPIs yet. Send me this full output.")


if __name__ == "__main__":
    main()

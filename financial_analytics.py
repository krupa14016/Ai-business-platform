from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

from db_connect import get_engine

TABLE = "annual_kpis_clean"

# Whitelist: only these names may ever be placed inside a SQL query.
# This stops anyone sending a "metric" like  revenue; DROP TABLE ...
METRICS = {
    "revenue", "gross_profit", "operating_income", "net_income",
    "total_assets", "total_liabilities", "current_assets",
    "current_liabilities", "equity", "cash",
    "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
    "revenue_growth_pct", "net_income_growth_pct", "current_ratio",
    "liabilities_to_equity", "roe_pct", "roa_pct",
}


def _convert(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _rows(sql, params=None):
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [{k: _convert(v) for k, v in row.items()} for row in result.mappings()]


def _check_metric(metric):
    if metric not in METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Allowed: {sorted(METRICS)}")
    return metric


def list_metrics():
    return sorted(METRICS)


def get_all_kpis():
    return _rows(f"SELECT * FROM {TABLE} ORDER BY period_end")


def get_kpis_for_year(fiscal_year):
    rows = _rows(f"SELECT * FROM {TABLE} WHERE fiscal_year = :y", {"y": fiscal_year})
    return rows[0] if rows else None


def get_metric_trend(metric, start_year=None, end_year=None):
    col = _check_metric(metric)
    rows = _rows(f"""SELECT fiscal_year, period_end, {col} AS value
                     FROM {TABLE} WHERE {col} IS NOT NULL ORDER BY period_end""")
    if start_year is not None:
        rows = [r for r in rows if r["fiscal_year"] >= start_year]
    if end_year is not None:
        rows = [r for r in rows if r["fiscal_year"] <= end_year]
    return rows


def get_best_year(metric):
    col = _check_metric(metric)
    rows = _rows(f"""SELECT fiscal_year, period_end, {col} AS value
                     FROM {TABLE} WHERE {col} IS NOT NULL
                     ORDER BY {col} DESC LIMIT 1""")
    return rows[0] if rows else None


def compare_years(metric, year_a, year_b):
    col = _check_metric(metric)
    a = get_kpis_for_year(year_a)
    b = get_kpis_for_year(year_b)
    if a is None or b is None:
        return None
    va, vb = a[col], b[col]
    result = {"metric": metric, "year_a": year_a, "value_a": va,
              "year_b": year_b, "value_b": vb, "change": None, "change_pct": None}
    if va is not None and vb is not None:
        result["change"] = round(vb - va, 2)
        if va != 0:
            result["change_pct"] = round((vb - va) / abs(va) * 100, 2)
    return result


def get_summary():
    rows = _rows(f"SELECT * FROM {TABLE} ORDER BY period_end DESC LIMIT 1")
    if not rows:
        return None
    r = rows[0]
    keep = ["fiscal_year", "period_end", "revenue", "net_income", "gross_margin_pct",
            "net_margin_pct", "revenue_growth_pct", "current_ratio", "liabilities_to_equity"]
    return {k: r[k] for k in keep}

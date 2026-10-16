import sys

import pandas as pd
from sqlalchemy import text

from db_connect import get_engine

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ->  {detail}" if detail else ""))


def header(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def to_float(series):
    return series.map(lambda v: float(v) if v is not None and not pd.isna(v) else float("nan"))


# ============================================================
# 1. BUILD THE KPI TABLE WITH SQL
# ============================================================

CREATE_SQL = """
CREATE TABLE annual_kpis_clean AS
WITH flows AS (
    SELECT
        period_end,
        MAX(fiscal_year) AS fiscal_year,
        MAX(value) FILTER (WHERE metric = 'revenue')          AS revenue,
        MAX(value) FILTER (WHERE metric = 'gross_profit')     AS gross_profit,
        MAX(value) FILTER (WHERE metric = 'operating_income') AS operating_income,
        MAX(value) FILTER (WHERE metric = 'net_income')       AS net_income
    FROM financial_facts_clean
    WHERE record_type = 'annual_flow'
    GROUP BY period_end
),
balances AS (
    SELECT
        period_end,
        MAX(value) FILTER (WHERE metric = 'assets')              AS total_assets,
        MAX(value) FILTER (WHERE metric = 'liabilities')         AS total_liabilities,
        MAX(value) FILTER (WHERE metric = 'current_assets')      AS current_assets,
        MAX(value) FILTER (WHERE metric = 'current_liabilities') AS current_liabilities,
        MAX(value) FILTER (WHERE metric = 'equity')              AS equity,
        MAX(value) FILTER (WHERE metric = 'cash')                AS cash
    FROM financial_facts_clean
    WHERE record_type = 'balance_snapshot'
    GROUP BY period_end
),
joined AS (
    SELECT f.period_end, f.fiscal_year, f.revenue, f.gross_profit,
           f.operating_income, f.net_income,
           b.total_assets, b.total_liabilities, b.current_assets,
           b.current_liabilities, b.equity, b.cash
    FROM flows f
    LEFT JOIN balances b ON b.period_end = f.period_end
),
with_prev AS (
    SELECT j.*,
           LAG(j.period_end) OVER w AS prev_period_end,
           LAG(j.revenue)    OVER w AS prev_revenue,
           LAG(j.net_income) OVER w AS prev_net_income
    FROM joined j
    WINDOW w AS (ORDER BY j.period_end)
)
SELECT
    fiscal_year, period_end,
    revenue, gross_profit, operating_income, net_income,
    total_assets, total_liabilities, current_assets, current_liabilities,
    equity, cash,
    ROUND(gross_profit     / NULLIF(revenue, 0) * 100, 2) AS gross_margin_pct,
    ROUND(operating_income / NULLIF(revenue, 0) * 100, 2) AS operating_margin_pct,
    ROUND(net_income       / NULLIF(revenue, 0) * 100, 2) AS net_margin_pct,
    CASE WHEN (period_end - prev_period_end) BETWEEN 350 AND 380
         THEN ROUND((revenue - prev_revenue) / NULLIF(prev_revenue, 0) * 100, 2)
    END AS revenue_growth_pct,
    CASE WHEN (period_end - prev_period_end) BETWEEN 350 AND 380 AND prev_net_income > 0
         THEN ROUND((net_income - prev_net_income) / prev_net_income * 100, 2)
    END AS net_income_growth_pct,
    ROUND(current_assets  / NULLIF(current_liabilities, 0), 2) AS current_ratio,
    ROUND(total_liabilities / NULLIF(equity, 0), 2)            AS liabilities_to_equity,
    ROUND(net_income / NULLIF(equity, 0) * 100, 2)             AS roe_pct,
    ROUND(net_income / NULLIF(total_assets, 0) * 100, 2)       AS roa_pct
FROM with_prev
ORDER BY period_end
"""

STATEMENTS = [
    "DROP TABLE IF EXISTS annual_kpis_clean",
    CREATE_SQL,
    "ALTER TABLE annual_kpis_clean ADD PRIMARY KEY (period_end)",
]


def build(engine):
    header("BUILDING annual_kpis_clean")
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
        n = conn.execute(text("SELECT COUNT(*) FROM annual_kpis_clean")).scalar()
    print(f"Table annual_kpis_clean created with {n} rows.")


# ============================================================
# 2. INDEPENDENT RECALCULATION IN PANDAS (second opinion)
# ============================================================

def expected_values(conn):
    facts = pd.read_sql(text(
        "SELECT record_type, metric, period_end, value FROM financial_facts_clean"), conn)
    facts["value"] = to_float(facts["value"])
    facts["period_end"] = pd.to_datetime(facts["period_end"])

    flows = facts[facts["record_type"] == "annual_flow"].pivot_table(
        index="period_end", columns="metric", values="value", aggfunc="max")
    bal = facts[facts["record_type"] == "balance_snapshot"].pivot_table(
        index="period_end", columns="metric", values="value", aggfunc="max")
    exp = flows.join(bal, how="left").sort_index()

    def pct(a, b):
        return a / b.where(b != 0) * 100

    exp["gross_margin_pct"] = pct(exp["gross_profit"], exp["revenue"])
    exp["operating_margin_pct"] = pct(exp["operating_income"], exp["revenue"])
    exp["net_margin_pct"] = pct(exp["net_income"], exp["revenue"])

    gap = exp.index.to_series().diff().dt.days
    one_year = gap.between(350, 380)
    prev_rev = exp["revenue"].shift(1)
    prev_ni = exp["net_income"].shift(1)
    exp["revenue_growth_pct"] = ((exp["revenue"] - prev_rev)
                                 / prev_rev.where(prev_rev != 0) * 100).where(one_year)
    exp["net_income_growth_pct"] = ((exp["net_income"] - prev_ni)
                                    / prev_ni.where(prev_ni > 0) * 100).where(one_year)
    exp["current_ratio"] = exp["current_assets"] / exp["current_liabilities"].where(
        exp["current_liabilities"] != 0)
    exp["liabilities_to_equity"] = exp["liabilities"] / exp["equity"].where(exp["equity"] != 0)
    exp["roe_pct"] = pct(exp["net_income"], exp["equity"])
    exp["roa_pct"] = pct(exp["net_income"], exp["assets"])
    return exp


def validate(engine):
    header("CHECK GROUP C: KPI TABLE VALIDATION")
    with engine.connect() as conn:
        def scalar(sql):
            return conn.execute(text(sql)).scalar()

        n_kpi = scalar("SELECT COUNT(*) FROM annual_kpis_clean")
        n_flow = scalar("""SELECT COUNT(DISTINCT period_end) FROM financial_facts_clean
                           WHERE record_type = 'annual_flow'""")
        check("One KPI row per annual period", n_kpi == n_flow, f"{n_kpi} vs {n_flow}")

        dup_years = scalar("""SELECT COUNT(*) FROM (SELECT fiscal_year FROM annual_kpis_clean
                              GROUP BY fiscal_year HAVING COUNT(*) > 1) d""")
        check("No duplicate fiscal years", dup_years == 0)

        bad_year = scalar("""SELECT COUNT(*) FROM annual_kpis_clean
                             WHERE fiscal_year <> EXTRACT(YEAR FROM period_end)""")
        check("fiscal_year matches the year of period_end", bad_year == 0, f"{bad_year} mismatches")

        n_rev = scalar("SELECT COUNT(revenue) FROM annual_kpis_clean")
        n_rev_src = scalar("""SELECT COUNT(DISTINCT period_end) FROM financial_facts_clean
                              WHERE record_type = 'annual_flow' AND metric = 'revenue'""")
        check("Revenue rows in KPI table = revenue rows in facts", n_rev == n_rev_src,
              f"{n_rev} vs {n_rev_src}")

        out_of_range = scalar("""SELECT COUNT(*) FROM annual_kpis_clean WHERE
                gross_margin_pct NOT BETWEEN -100 AND 100
             OR operating_margin_pct NOT BETWEEN -100 AND 100
             OR net_margin_pct NOT BETWEEN -100 AND 100
             OR current_ratio NOT BETWEEN 0 AND 20""")
        check("Margins within -100..100 and current ratio within 0..20", out_of_range == 0,
              f"{out_of_range} rows outside range")

        actual = pd.read_sql(text("SELECT * FROM annual_kpis_clean ORDER BY period_end"), conn)
        actual["period_end"] = pd.to_datetime(actual["period_end"])
        actual = actual.set_index("period_end")

        exp = expected_values(conn)
        actual = actual.reindex(exp.index)

        pairs = [
            ("revenue", "revenue", 0.5), ("gross_profit", "gross_profit", 0.5),
            ("operating_income", "operating_income", 0.5), ("net_income", "net_income", 0.5),
            ("total_assets", "assets", 0.5), ("total_liabilities", "liabilities", 0.5),
            ("current_assets", "current_assets", 0.5),
            ("current_liabilities", "current_liabilities", 0.5),
            ("equity", "equity", 0.5), ("cash", "cash", 0.5),
            ("gross_margin_pct", "gross_margin_pct", 0.006),
            ("operating_margin_pct", "operating_margin_pct", 0.006),
            ("net_margin_pct", "net_margin_pct", 0.006),
            ("revenue_growth_pct", "revenue_growth_pct", 0.006),
            ("net_income_growth_pct", "net_income_growth_pct", 0.006),
            ("current_ratio", "current_ratio", 0.006),
            ("liabilities_to_equity", "liabilities_to_equity", 0.006),
            ("roe_pct", "roe_pct", 0.006), ("roa_pct", "roa_pct", 0.006),
        ]
        for table_col, exp_col, tol in pairs:
            a = to_float(actual[table_col])
            e = exp[exp_col].astype(float)
            ok = (a.isna() & e.isna()) | ((a - e).abs() <= tol)
            check(f"{table_col} matches independent recalculation", bool(ok.all()),
                  f"{int((~ok).sum())} mismatches")

        old = scalar("SELECT COUNT(*) FROM annual_kpis")
        check("Old annual_kpis table untouched (17 rows)", old == 17, f"{old} rows")

        header("INFO: KPI TABLE (money in billions of USD)")
        view = pd.read_sql(text("""
            SELECT fiscal_year, revenue, net_income, gross_margin_pct, operating_margin_pct,
                   net_margin_pct, revenue_growth_pct, current_ratio,
                   liabilities_to_equity, roe_pct
            FROM annual_kpis_clean ORDER BY period_end"""), conn)
        for col in view.columns[1:]:
            view[col] = to_float(view[col])
        view["revenue"] = (view["revenue"] / 1e9).round(1)
        view["net_income"] = (view["net_income"] / 1e9).round(1)
        print(view.to_string(index=False))


def main():
    engine = get_engine()
    build(engine)
    validate(engine)
    header("FINAL RESULT")
    print(f"{sum(RESULTS)} of {len(RESULTS)} checks passed")
    if all(RESULTS):
        print("ALL CHECKS PASSED. KPI table is verified.")
    else:
        print("Some checks FAILED. Send me this full output before going further.")
        sys.exit(1)


if __name__ == "__main__":
    main()

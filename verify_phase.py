from sqlalchemy import text, inspect
from db_connect import get_engine

print("=" * 65)
print("AI-BI PLATFORM: DATABASE AND ML VERIFICATION")
print("=" * 65)

engine = get_engine()

# 1. Test the real database connection
with engine.connect() as conn:
    result = conn.execute(
        text("SELECT current_database(), current_user, version()")
    ).fetchone()

    print("\n[1] DATABASE CONNECTION")
    print("Database:", result[0])
    print("User:", result[1])
    print("PostgreSQL:", result[2].split(",")[0])

    assert result[0] == "ai_bi_platform", (
        f"Wrong database: {result[0]}"
    )
    print("PASS")

# 2. Verify the KPI table and its columns
inspector = inspect(engine)
tables = inspector.get_table_names()

print("\n[2] KPI TABLE")
print("annual_kpis_clean exists:", "annual_kpis_clean" in tables)
assert "annual_kpis_clean" in tables, "Verified KPI table is missing"

columns = {
    col["name"] for col in inspector.get_columns("annual_kpis_clean")
}
print("Columns:", sorted(columns))

required = {
    "fiscal_year", "revenue", "gross_profit",
    "operating_income", "net_income", "total_assets",
    "total_liabilities", "equity", "cash",
    "gross_margin_pct", "operating_margin_pct",
    "net_margin_pct", "current_ratio", "liabilities_to_equity",
}
missing = required - columns
assert not missing, f"Missing KPI columns: {sorted(missing)}"
print("Required columns: PASS")

# 3. Verify the KPI rows and fiscal-year uniqueness
with engine.connect() as conn:
    count = conn.execute(
        text("SELECT COUNT(*) FROM annual_kpis_clean")
    ).scalar_one()

    duplicate_years = conn.execute(text("""
        SELECT fiscal_year, COUNT(*) AS n
        FROM annual_kpis_clean
        GROUP BY fiscal_year
        HAVING COUNT(*) > 1
    """)).fetchall()

    null_years = conn.execute(text("""
        SELECT COUNT(*)
        FROM annual_kpis_clean
        WHERE fiscal_year IS NULL
    """)).scalar_one()

print("\n[3] KPI DATA QUALITY")
print("KPI rows:", count)
print("Duplicate fiscal years:", len(duplicate_years))
print("Null fiscal years:", null_years)

assert count >= 2, "Not enough KPI rows for trend/forecast testing"
assert not duplicate_years, "Duplicate fiscal years found"
assert null_years == 0, "Null fiscal years found"
print("PASS")

# 4. Test the application DatabaseManager and analytics functions
print("\n[4] ML/ANALYTICS FUNCTIONS")

from ml_engine import (
    AnalyticsEngine,
    AnomalyDetector,
    FinancialForecaster,
)

tests = [
    ("Profitability trend", AnalyticsEngine.get_profitability_trend),
    ("Financial health trend", AnalyticsEngine.get_financial_health_trend),
    ("Anomaly detection", AnomalyDetector.detect_kpi_anomalies),
    ("Net income forecast", FinancialForecaster.forecast_net_income),
]

for name, function in tests:
    try:
        output = function()
        assert isinstance(output, (list, dict)), (
            f"Unexpected output type: {type(output).__name__}"
        )
        if name == "Net income forecast":
            assert len(output["forecast"]) == 3
            print(
                f"PASS - {name}: "
                f"{output['historical_years']} historical years, "
                f"{len(output['forecast'])} forecast years"
            )
        else:
            print(f"PASS - {name}: {len(output)} result(s)")
    except Exception as exc:
        print(f"FAIL - {name}: {type(exc).__name__}: {exc}")
        raise

print("\n" + "=" * 65)
print("ALL DATABASE AND ML CHECKS PASSED")
print("=" * 65)

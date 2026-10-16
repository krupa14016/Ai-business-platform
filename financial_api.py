from fastapi import FastAPI, HTTPException
from sqlalchemy import text

import financial_analytics as fa
from db_connect import get_engine

app = FastAPI(
    title="AI-BI Financial API",
    description="Apple financial KPIs served from PostgreSQL",
    version="1.0.0",
)


@app.get("/health")
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database not reachable")
    return {"status": "healthy", "database": "connected"}


@app.get("/metrics")
def metrics():
    return {"metrics": fa.list_metrics()}


@app.get("/summary")
def summary():
    return fa.get_summary()


@app.get("/kpis")
def all_kpis():
    return fa.get_all_kpis()


@app.get("/kpis/{fiscal_year}")
def kpis_for_year(fiscal_year: int):
    row = fa.get_kpis_for_year(fiscal_year)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No data for fiscal year {fiscal_year}")
    return row


@app.get("/metrics/{metric}/trend")
def trend(metric: str, start_year: int | None = None, end_year: int | None = None):
    try:
        return fa.get_metric_trend(metric, start_year, end_year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/metrics/{metric}/best")
def best(metric: str):
    try:
        row = fa.get_best_year(metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=404, detail="No data for this metric")
    return row


@app.get("/compare")
def compare(metric: str, year_a: int, year_b: int):
    try:
        result = fa.compare_years(metric, year_a, year_b)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="One of the years has no data")
    return result

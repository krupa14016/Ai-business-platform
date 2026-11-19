
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import DatabaseManager
from ai_engine import AIQueryEngine
from ml_engine import AnomalyDetector, FinancialForecaster, AnalyticsEngine
from business_insights import build_financial_insights
from ollama_client import explain_verified_result


app = FastAPI(
    title="AI Business Intelligence Platform",
    description=(
        "AI BI Platform using PostgreSQL, annual financial KPIs, "
        "anomaly detection, forecasting, and AI-powered queries."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatQueryRequest(BaseModel):
    question: str


def _json_value(value: Any) -> Any:
    """Convert database values into JSON-safe Python values."""

    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, bool):
        return value

    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return float(value)

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, int):
        return value

    # Handle other numeric types, if returned by a database driver.
    if hasattr(value, "__float__"):
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError, OverflowError):
            return str(value)

    return value


def clean_for_json(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of database result dictionaries to JSON-safe values."""

    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in rows
    ]


def _database_type() -> str:
    return str(DatabaseManager.get_db_type()).upper()


# ============================================================
# ROOT AND HEALTH
# ============================================================

@app.get("/")
def home():
    return {
        "message": "AI BI Platform v2.0 is active",
        "database_engine": _database_type(),
        "docs_url": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
def health_check():
    """Check the actual database connection."""

    try:
        result = DatabaseManager.execute_query(
            "SELECT 1 AS connected;"
        )

        if not result:
            raise RuntimeError(
                "The database health query returned no result."
            )

        return {
            "status": "healthy",
            "database_connected": True,
            "database_engine": _database_type(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database_connected": False,
                "error": str(exc),
            },
        ) from exc


# ============================================================
# BI ANALYTICS ENDPOINTS
# ============================================================

@app.get("/api/analytics/summary")
def get_analytics_summary():
    """Return a high-level summary from PostgreSQL."""

    try:
        total_rows = DatabaseManager.execute_query(
            "SELECT COUNT(*) AS total FROM financial_facts;"
        )

        total_facts = (
            int(total_rows[0]["total"])
            if total_rows and total_rows[0].get("total") is not None
            else 0
        )

        year_rows = DatabaseManager.execute_query(
            """
            SELECT
                MIN(fiscal_year) AS min_year,
                MAX(fiscal_year) AS max_year
            FROM annual_kpis_clean;
            """
        )

        year_row = year_rows[0] if year_rows else {}
        min_year = year_row.get("min_year")
        max_year = year_row.get("max_year")

        best_rows = DatabaseManager.execute_query(
            """
            SELECT fiscal_year, net_income
            FROM annual_kpis_clean
            WHERE net_income IS NOT NULL
            ORDER BY net_income DESC, fiscal_year DESC
            LIMIT 1;
            """
        )

        best = best_rows[0] if best_rows else {}

        year_range = (
            f"{int(min_year)} - {int(max_year)}"
            if min_year is not None and max_year is not None
            else "N/A"
        )

        return {
            "company": "Apple Inc.",
            "database_engine": _database_type(),
            "total_financial_facts": total_facts,
            "annual_kpi_rows": len(
                DatabaseManager.execute_query(
                    "SELECT fiscal_year FROM annual_kpis_clean;"
                )
            ),
            "fiscal_year_range": year_range,
            "highest_net_income_year": (
                int(best["fiscal_year"])
                if best.get("fiscal_year") is not None
                else None
            ),
            "highest_net_income_usd": _json_value(
                best.get("net_income")
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve analytics summary: {exc}",
        ) from exc


@app.get("/api/analytics/kpis")
def get_annual_kpis(
    limit: int = Query(default=10, ge=1, le=50)
):
    """Return annual KPI rows, newest fiscal year first."""

    try:
        rows = DatabaseManager.execute_query(
            """
            SELECT *
            FROM annual_kpis_clean
            ORDER BY fiscal_year DESC
            LIMIT %s;
            """,
            (limit,),
        )

        return clean_for_json(rows)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve annual KPIs: {exc}",
        ) from exc


@app.get("/api/analytics/facts")
def get_financial_facts(
    metric: Optional[str] = Query(
        default=None,
        description="Metric name, for example net_income or gross_profit",
    ),
    fiscal_year: Optional[int] = Query(
        default=None,
        description="Fiscal year, for example 2024",
    ),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return filtered raw financial facts from PostgreSQL."""

    query = """
        SELECT
            f.metric,
            f.value,
            f.unit,
            f.fiscal_year,
            f.fiscal_period,
            f.form,
            f.filing_date,
            c.name AS company_name
        FROM financial_facts AS f
        JOIN companies AS c ON f.company_id = c.id
        WHERE 1 = 1
    """

    params = []

    if metric:
        query += " AND f.metric = %s"
        params.append(metric)

    if fiscal_year is not None:
        query += " AND f.fiscal_year = %s"
        params.append(fiscal_year)

    query += """
        ORDER BY f.fiscal_year DESC, f.filing_date DESC
        LIMIT %s;
    """
    params.append(limit)

    try:
        rows = DatabaseManager.execute_query(query, tuple(params))
        return clean_for_json(rows)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve financial facts: {exc}",
        ) from exc


@app.get("/api/analytics/trend/profitability")
def get_profitability_trend():
    """Return annual revenue, income, and profitability-margin trends."""

    try:
        rows = AnalyticsEngine.get_profitability_trend()
        return clean_for_json(rows)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve profitability trends: {exc}",
        ) from exc


@app.get("/api/analytics/trend/health")
def get_financial_health_trend():
    """Return annual assets, liabilities, cash, and ratio trends."""

    try:
        rows = AnalyticsEngine.get_financial_health_trend()
        return clean_for_json(rows)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve financial-health trends: {exc}",
        ) from exc


# ============================================================
# ML ENDPOINTS
# ============================================================

@app.get("/api/ml/anomalies")
def get_anomalies():
    """Identify unusual annual net-income growth using z-scores."""

    try:
        anomalies = AnomalyDetector.detect_kpi_anomalies()

        return {
            "total_anomalies_detected": len(anomalies),
            "method": "Z-score",
            "threshold": AnomalyDetector.THRESHOLD,
            "anomalies": clean_for_json(anomalies),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {exc}",
        ) from exc


@app.get("/api/ml/forecast")
def get_forecast(
    years: int = Query(default=3, ge=1, le=10)
):
    """Forecast net income using a linear historical trend."""

    try:
        return FinancialForecaster.forecast_net_income(
            future_years=years
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecasting failed: {exc}",
        ) from exc

# ============================================================
# FINANCIAL INSIGHTS
# ============================================================

@app.get("/api/analytics/insights")
def get_financial_insights():
    """
    Return historical financial observations,
    evidence-based recommendations, and data gaps.
    """

    try:
        report = build_financial_insights()

        if report.get("status") == "unavailable":
            return report

        return report

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not generate financial insights: {exc}",
        ) from exc

# ============================================================
# AI CHAT ENDPOINT
# ============================================================


@app.post("/api/chat/query")
def process_chat_query(payload: ChatQueryRequest):
    """
    Process financial questions using verified PostgreSQL results.
    Ollama provides optional explanations without changing verified data.
    """

    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        # Step 1: Retrieve verified financial results.
        result = AIQueryEngine.process_question(question)

        # Step 2: Preserve the original result.
        response = dict(result)

        response["ai_explanation"] = None

        # Step 3: Identify the verified database source.
        if (
            result.get("status") == "success"
            and result.get("database") == "postgresql"
        ):
            response["ai_provider"] = "postgresql"

            # Step 4: Generate an optional explanation using Ollama.
            try:
                explanation = explain_verified_result(
                    question,
                    result,
                )

                if explanation:
                    response["ai_explanation"] = explanation
                    response["ai_provider"] = "ollama"

            except Exception as ollama_error:
                # Preserve the verified PostgreSQL answer.
                print(
                    "Ollama explanation unavailable: "
                    f"{ollama_error}"
                )

        else:
            response["ai_provider"] = "not_applicable"

        return response

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not process the question: {exc}",
        ) from exc

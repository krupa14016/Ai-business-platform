
"""Analytics, anomaly detection, and forecasting for the AI-BI Platform.

The verified PostgreSQL table annual_kpis_clean is the source of truth.
"""

import math
from typing import Any, Dict, List

from database import DatabaseManager


class AnalyticsEngine:
    """Read annual profitability and financial-health KPIs."""

    @staticmethod
    def get_profitability_trend() -> List[Dict[str, Any]]:
        return DatabaseManager.execute_query(
            """
            SELECT
                fiscal_year,
                revenue,
                gross_profit,
                operating_income,
                net_income,
                gross_margin_pct,
                operating_margin_pct,
                net_margin_pct
            FROM annual_kpis_clean
            ORDER BY fiscal_year ASC
            """
        )

    @staticmethod
    def get_financial_health_trend() -> List[Dict[str, Any]]:
        return DatabaseManager.execute_query(
            """
            SELECT
                fiscal_year,
                total_assets AS assets,
                total_liabilities AS liabilities,
                equity,
                cash,
                current_ratio,
                liabilities_to_equity AS debt_to_equity
            FROM annual_kpis_clean
            ORDER BY fiscal_year ASC
            """
        )


class AnomalyDetector:
    """Flag unusual year-over-year net-income growth using z-scores."""

    THRESHOLD = 1.8

    @staticmethod
    def detect_kpi_anomalies() -> List[Dict[str, Any]]:
        rows = DatabaseManager.execute_query(
            """
            SELECT
                fiscal_year,
                net_income,
                net_income_growth_pct AS net_income_yoy_growth_pct
            FROM annual_kpis_clean
            WHERE net_income IS NOT NULL
            ORDER BY fiscal_year ASC
            """
        )

        changes = []

        for row in rows:
            value = row.get("net_income_yoy_growth_pct")

            if value is None:
                continue

            value = float(value)

            if math.isfinite(value):
                changes.append((row, value))

        if len(changes) < 3:
            return []

        values = [value for _, value in changes]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        stddev = math.sqrt(variance)

        if stddev == 0:
            return []

        results = []

        for row, value in changes:
            z_score = (value - mean) / stddev

            if abs(z_score) >= AnomalyDetector.THRESHOLD:
                results.append(
                    {
                        "fiscal_year": row["fiscal_year"],
                        "metric": "net_income_yoy_growth_pct",
                        "value": value,
                        "z_score": round(z_score, 3),
                    }
                )

        return results


class FinancialForecaster:
    """Forecast net income using a simple linear trend."""

    @staticmethod
    def forecast_net_income(future_years: int = 3) -> Dict[str, Any]:
        if not isinstance(future_years, int) or isinstance(future_years, bool):
            raise ValueError("future_years must be an integer from 1 to 10")

        if not 1 <= future_years <= 10:
            raise ValueError("future_years must be between 1 and 10")

        rows = DatabaseManager.execute_query(
            """
            SELECT fiscal_year, net_income
            FROM annual_kpis_clean
            WHERE fiscal_year IS NOT NULL
              AND net_income IS NOT NULL
            ORDER BY fiscal_year ASC
            """
        )

        points = []

        for row in rows:
            year = row.get("fiscal_year")
            income = row.get("net_income")

            if year is None or income is None:
                continue

            year = float(year)
            income = float(income)

            if math.isfinite(year) and math.isfinite(income):
                points.append((year, income))

        if len(points) < 2:
            raise ValueError(
                "At least two valid annual net-income records are required"
            )

        x_mean = sum(year for year, _ in points) / len(points)
        y_mean = sum(income for _, income in points) / len(points)

        denominator = sum(
            (year - x_mean) ** 2 for year, _ in points
        )

        if denominator == 0:
            raise ValueError("Cannot forecast without distinct fiscal years")

        slope = sum(
            (year - x_mean) * (income - y_mean)
            for year, income in points
        ) / denominator

        intercept = y_mean - slope * x_mean
        last_year = int(max(year for year, _ in points))

        forecasts = []

        for offset in range(1, future_years + 1):
            forecast_year = last_year + offset
            predicted_income = intercept + slope * forecast_year

            forecasts.append(
                {
                    "fiscal_year": forecast_year,
                    "net_income": round(predicted_income, 2),
                }
            )

        return {
            "metric": "net_income",
            "method": "linear_trend",
            "historical_years": len(points),
            "forecast": forecasts,
            "disclaimer": (
                "These are statistical estimates, not guaranteed results "
                "or official company guidance."
            ),
        }

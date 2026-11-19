
import financial_analytics as analytics


# Metrics used for descriptive financial analysis.
INSIGHT_METRICS = {
    "revenue": {
        "label": "Revenue",
        "type": "money",
    },
    "gross_profit": {
        "label": "Gross profit",
        "type": "money",
    },
    "operating_income": {
        "label": "Operating income",
        "type": "money",
    },
    "net_income": {
        "label": "Net income",
        "type": "money",
    },
    "gross_margin_pct": {
        "label": "Gross margin",
        "type": "percentage",
    },
    "operating_margin_pct": {
        "label": "Operating margin",
        "type": "percentage",
    },
    "net_margin_pct": {
        "label": "Net margin",
        "type": "percentage",
    },
    "revenue_growth_pct": {
        "label": "Revenue growth",
        "type": "percentage",
    },
    "net_income_growth_pct": {
        "label": "Net income growth",
        "type": "percentage",
    },
    "current_ratio": {
        "label": "Current ratio",
        "type": "ratio",
    },
    "liabilities_to_equity": {
        "label": "Liabilities-to-equity ratio",
        "type": "ratio",
    },
    "roe_pct": {
        "label": "Return on equity",
        "type": "percentage",
    },
    "roa_pct": {
        "label": "Return on assets",
        "type": "percentage",
    },
}


def _get_available_values(rows, metric):
    """Return non-null observations for one metric, ordered by year."""
    return [
        row
        for row in rows
        if row.get(metric) is not None
    ]


def _format_value(value, metric):
    """Format a financial value for readable output."""
    metric_type = INSIGHT_METRICS[metric]["type"]

    if metric_type == "money":
        return f"${value / 1_000_000_000:,.2f} billion"

    if metric_type == "percentage":
        return f"{value:,.2f}%"

    if metric_type == "ratio":
        return f"{value:,.2f}x"

    return str(value)


def _analyze_metric(rows, metric):
    """
    Compare the two latest available non-null observations.
    Missing years are not treated as zero.
    """
    observations = _get_available_values(rows, metric)

    if not observations:
        return {
            "metric": metric,
            "label": INSIGHT_METRICS[metric]["label"],
            "status": "unavailable",
            "observations_count": 0,
            "latest": None,
            "previous": None,
            "change": None,
            "change_pct": None,
            "direction": "unavailable",
        }

    latest = observations[-1]

    result = {
        "metric": metric,
        "label": INSIGHT_METRICS[metric]["label"],
        "status": "available",
        "observations_count": len(observations),
        "latest": {
            "fiscal_year": latest["fiscal_year"],
            "value": latest[metric],
        },
        "previous": None,
        "change": None,
        "change_pct": None,
        "direction": "insufficient_history",
    }

    if len(observations) < 2:
        return result

    previous = observations[-2]

    latest_value = latest[metric]
    previous_value = previous[metric]
    change = latest_value - previous_value

    result["previous"] = {
        "fiscal_year": previous["fiscal_year"],
        "value": previous_value,
    }

    result["change"] = round(change, 4)

    if change > 0:
        result["direction"] = "increased"
    elif change < 0:
        result["direction"] = "decreased"
    else:
        result["direction"] = "unchanged"

    if INSIGHT_METRICS[metric]["type"] == "percentage":
        result["change_unit"] = "percentage_points"
    else:
        result["change_unit"] = (
            "currency" if INSIGHT_METRICS[metric]["type"] == "money"
            else "ratio_points"
        )

    metric_type = INSIGHT_METRICS[metric]["type"]

    if metric_type != "percentage" and previous_value > 0:
        result["change_pct"] = round(
            (change / previous_value) * 100,
            2,
        )

    return result


def _build_observations(analyses):
    """Create factual observations from calculated metric changes."""
    observations = []

    for metric, analysis in analyses.items():
        if analysis["status"] != "available":
            continue

        latest = analysis["latest"]
        previous = analysis["previous"]

        if previous is None:
            continue

        label = analysis["label"]
        latest_year = latest["fiscal_year"]
        previous_year = previous["fiscal_year"]

        latest_text = _format_value(latest["value"], metric)
        previous_text = _format_value(previous["value"], metric)

        direction = analysis["direction"]

        if direction == "unchanged":
            message = (
                f"{label} remained unchanged at {latest_text} "
                f"between FY{previous_year} and FY{latest_year}."
            )
        else:
            message = (
                f"{label} {direction} from {previous_text} "
                f"in FY{previous_year} to {latest_text} "
                f"in FY{latest_year}."
            )

        observations.append({
            "metric": metric,
            "type": "factual_observation",
            "message": message,
            "evidence": {
                "previous_year": previous_year,
                "previous_value": previous["value"],
                "latest_year": latest_year,
                "latest_value": latest["value"],
                "change": analysis["change"],
                "change_pct": analysis["change_pct"],
                "change_unit": analysis.get("change_unit"),
            },
        })

    return observations


def _build_recommendations(analyses):
    """
    Produce conservative monitoring recommendations.
    These do not claim causes or provide investment advice.
    """
    recommendations = []

    revenue_growth = analyses["revenue_growth_pct"]
    net_income_growth = analyses["net_income_growth_pct"]
    current_ratio = analyses["current_ratio"]
    leverage = analyses["liabilities_to_equity"]
    operating_margin = analyses["operating_margin_pct"]

    if (
        revenue_growth["status"] == "available"
        and revenue_growth["previous"] is not None
        and revenue_growth["direction"] == "decreased"
    ):
        recommendations.append({
            "area": "Revenue",
            "priority": "monitor",
            "recommendation": (
                "Monitor revenue growth in upcoming reporting periods "
                "to determine whether the decline continues."
            ),
            "evidence_metrics": ["revenue_growth_pct"],
        })

    if (
        net_income_growth["status"] == "available"
        and net_income_growth["previous"] is not None
        and net_income_growth["direction"] == "decreased"
    ):
        recommendations.append({
            "area": "Profitability",
            "priority": "monitor",
            "recommendation": (
                "Review future net income growth and compare it with "
                "revenue and operating margin movements."
            ),
            "evidence_metrics": ["net_income_growth_pct", "revenue_growth_pct", "operating_margin_pct"],
        })

    if (
        current_ratio["status"] == "available"
        and current_ratio["latest"] is not None
        and current_ratio["latest"]["value"] < 1
    ):
        recommendations.append({
            "area": "Liquidity",
            "priority": "review",
            "recommendation": (
                "Review current assets and current liabilities "
                "together to monitor short-term liquidity."
            ),
            "evidence_metrics": ["current_ratio", "current_assets", "current_liabilities"],
        })

    if (
        leverage["status"] == "available"
        and leverage["previous"] is not None
        and leverage["direction"] == "increased"
    ):
        recommendations.append({
            "area": "Leverage",
            "priority": "monitor",
            "recommendation": (
                "Monitor the liabilities-to-equity ratio and review "
                "the movement in total liabilities and equity."
            ),
            "evidence_metrics": ["liabilities_to_equity", "total_liabilities", "equity"],
        })

    if (
        operating_margin["status"] == "available"
        and operating_margin["previous"] is not None
        and operating_margin["direction"] == "decreased"
    ):
        recommendations.append({
            "area": "Operating profitability",
            "priority": "monitor",
            "recommendation": (
                "Review operating margin alongside revenue and "
                "operating income in subsequent reporting periods."
            ),
            "evidence_metrics": ["operating_margin_pct", "revenue", "operating_income"],
        })

    return recommendations


def build_financial_insights(rows=None):
    """
    Build a structured financial insights report.

    Uses all available annual records and skips missing metric values.
    PostgreSQL remains the source of truth.
    """
    if rows is None:
        rows = analytics.get_all_kpis()

    if not rows:
        return {
            "status": "unavailable",
            "message": "No annual financial records are available.",
            "latest_fiscal_year": None,
            "metrics": {},
            "observations": [],
            "recommendations": [],
            "data_gaps": [],
        }

    rows = sorted(
        rows,
        key=lambda row: row.get("fiscal_year", 0),
    )

    analyses = {
        metric: _analyze_metric(rows, metric)
        for metric in INSIGHT_METRICS
    }

    observations = _build_observations(analyses)
    recommendations = _build_recommendations(analyses)

    data_gaps = [
        {
            "metric": metric,
            "label": details["label"],
            "available_years": [
                row["fiscal_year"]
                for row in rows
                if row.get(metric) is not None
            ],
            "missing_years": [
                row["fiscal_year"]
                for row in rows
                if row.get(metric) is None
            ],
        }
        for metric, details in INSIGHT_METRICS.items()
        if any(row.get(metric) is None for row in rows)
    ]

    return {
        "status": "success",
        "latest_fiscal_year": rows[-1]["fiscal_year"],
        "historical_years": len(rows),
        "metrics": analyses,
        "observations": observations,
        "recommendations": recommendations,
        "data_gaps": data_gaps,
    }

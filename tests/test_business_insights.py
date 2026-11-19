
from unittest.mock import patch

from business_insights import build_financial_insights


def make_row(year, **overrides):
    row = {
        "fiscal_year": year,
        "revenue": None,
        "gross_profit": None,
        "operating_income": None,
        "net_income": None,
        "gross_margin_pct": None,
        "operating_margin_pct": None,
        "net_margin_pct": None,
        "revenue_growth_pct": None,
        "net_income_growth_pct": None,
        "current_ratio": None,
        "liabilities_to_equity": None,
        "roe_pct": None,
        "roa_pct": None,
    }
    row.update(overrides)
    return row


@patch("business_insights.analytics.get_all_kpis")
def test_latest_revenue_comparison(mock_kpis):
    mock_kpis.return_value = [
        make_row(2024, revenue=100_000_000_000),
        make_row(2025, revenue=110_000_000_000),
    ]

    result = build_financial_insights()

    revenue = result["metrics"]["revenue"]

    assert result["status"] == "success"
    assert result["latest_fiscal_year"] == 2025
    assert revenue["latest"]["value"] == 110_000_000_000
    assert revenue["previous"]["value"] == 100_000_000_000
    assert revenue["change_pct"] == 10.0
    assert revenue["direction"] == "increased"


@patch("business_insights.analytics.get_all_kpis")
def test_percentage_metrics_use_percentage_points(mock_kpis):
    mock_kpis.return_value = [
        make_row(2024, net_income_growth_pct=-3.36),
        make_row(2025, net_income_growth_pct=19.50),
    ]

    result = build_financial_insights()

    growth = result["metrics"]["net_income_growth_pct"]

    assert growth["change"] == 22.86
    assert growth["change_unit"] == "percentage_points"
    assert growth["change_pct"] is None


@patch("business_insights.analytics.get_all_kpis")
def test_missing_values_are_not_treated_as_zero(mock_kpis):
    mock_kpis.return_value = [
        make_row(2024, revenue=None),
        make_row(2025, revenue=100_000_000_000),
    ]

    result = build_financial_insights()

    revenue = result["metrics"]["revenue"]

    assert revenue["status"] == "available"
    assert revenue["observations_count"] == 1
    assert revenue["latest"]["value"] == 100_000_000_000
    assert revenue["previous"] is None
    assert revenue["direction"] == "insufficient_history"


@patch("business_insights.analytics.get_all_kpis")
def test_liquidity_recommendation(mock_kpis):
    mock_kpis.return_value = [
        make_row(2024, current_ratio=0.87),
        make_row(2025, current_ratio=0.89),
    ]

    result = build_financial_insights()

    liquidity = [
        item for item in result["recommendations"]
        if item["area"] == "Liquidity"
    ]

    assert len(liquidity) == 1
    assert liquidity[0]["priority"] == "review"
    assert "current_ratio" in liquidity[0]["evidence_metrics"]


@patch("business_insights.analytics.get_all_kpis")
def test_empty_dataset(mock_kpis):
    mock_kpis.return_value = []

    result = build_financial_insights()

    assert result["status"] == "unavailable"
    assert result["latest_fiscal_year"] is None
    assert result["observations"] == []
    assert result["recommendations"] == []

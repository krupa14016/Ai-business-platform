from unittest.mock import patch

import pytest

import financial_analytics as analytics


def test_list_metrics_returns_sorted_whitelist():
    result = analytics.list_metrics()

    assert result == sorted(analytics.METRICS)
    assert "revenue" in result
    assert "net_income" in result


@patch("financial_analytics._rows")
def test_get_all_kpis_returns_database_rows(mock_rows):
    expected = [
        {"fiscal_year": 2024, "revenue": 391035000000},
        {"fiscal_year": 2025, "revenue": 416161000000},
    ]
    mock_rows.return_value = expected

    result = analytics.get_all_kpis()

    assert result == expected
    mock_rows.assert_called_once()
    assert "annual_kpis_clean" in mock_rows.call_args[0][0]
    assert "ORDER BY period_end" in mock_rows.call_args[0][0]


@patch("financial_analytics._rows")
def test_get_kpis_for_year_returns_matching_row(mock_rows):
    expected = {"fiscal_year": 2025, "revenue": 416161000000}
    mock_rows.return_value = [expected]

    result = analytics.get_kpis_for_year(2025)

    assert result == expected
    mock_rows.assert_called_once()
    assert mock_rows.call_args[0][1] == {"y": 2025}


@patch("financial_analytics._rows")
def test_get_kpis_for_missing_year_returns_none(mock_rows):
    mock_rows.return_value = []

    result = analytics.get_kpis_for_year(1900)

    assert result is None


@patch("financial_analytics._rows")
def test_get_metric_trend_filters_year_range(mock_rows):
    mock_rows.return_value = [
        {"fiscal_year": 2022, "period_end": "2022-09-24", "value": 394000000000},
        {"fiscal_year": 2023, "period_end": "2023-09-30", "value": 383000000000},
        {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 391000000000},
        {"fiscal_year": 2025, "period_end": "2025-09-27", "value": 416000000000},
    ]

    result = analytics.get_metric_trend("revenue", 2023, 2024)

    assert [row["fiscal_year"] for row in result] == [2023, 2024]
    assert all("value" in row for row in result)


@patch("financial_analytics._rows")
def test_get_metric_trend_rejects_invalid_metric(mock_rows):
    with pytest.raises(ValueError, match="Unknown metric"):
        analytics.get_metric_trend("revenue; DROP TABLE annual_kpis_clean")

    mock_rows.assert_not_called()


@patch("financial_analytics._rows")
def test_get_best_year_returns_highest_value(mock_rows):
    expected = {
        "fiscal_year": 2025,
        "period_end": "2025-09-27",
        "value": 416161000000,
    }
    mock_rows.return_value = [expected]

    result = analytics.get_best_year("revenue")

    assert result == expected
    assert "ORDER BY revenue DESC" in mock_rows.call_args[0][0]


@patch("financial_analytics.get_kpis_for_year")
def test_compare_years_calculates_change_and_percentage(mock_year):
    mock_year.side_effect = [
        {"fiscal_year": 2023, "revenue": 383285000000},
        {"fiscal_year": 2024, "revenue": 391035000000},
    ]

    result = analytics.compare_years("revenue", 2023, 2024)

    assert result["value_a"] == 383285000000
    assert result["value_b"] == 391035000000
    assert result["change"] == 7750000000
    assert result["change_pct"] == 2.02


@patch("financial_analytics.get_kpis_for_year")
def test_compare_years_returns_none_when_year_missing(mock_year):
    mock_year.side_effect = [
        {"fiscal_year": 2023, "revenue": 383285000000},
        None,
    ]

    result = analytics.compare_years("revenue", 2023, 2024)

    assert result is None


@patch("financial_analytics.get_kpis_for_year")
def test_compare_years_handles_zero_baseline(mock_year):
    mock_year.side_effect = [
        {"fiscal_year": 2023, "revenue": 0},
        {"fiscal_year": 2024, "revenue": 100},
    ]

    result = analytics.compare_years("revenue", 2023, 2024)

    assert result["change"] == 100
    assert result["change_pct"] is None


@patch("financial_analytics._rows")
def test_get_summary_returns_latest_selected_metrics(mock_rows):
    expected = {
        "fiscal_year": 2025,
        "period_end": "2025-09-27",
        "revenue": 416161000000,
        "net_income": 112010000000,
        "gross_margin_pct": 46.91,
        "net_margin_pct": 26.92,
        "revenue_growth_pct": 6.43,
        "current_ratio": 0.89,
        "liabilities_to_equity": 3.87,
    }
    mock_rows.return_value = [expected]

    result = analytics.get_summary()

    assert result == expected
    assert result["fiscal_year"] == 2025
    assert "LIMIT 1" in mock_rows.call_args[0][0]


@patch("financial_analytics._rows")
def test_get_summary_returns_none_for_empty_database(mock_rows):
    mock_rows.return_value = []

    result = analytics.get_summary()

    assert result is None

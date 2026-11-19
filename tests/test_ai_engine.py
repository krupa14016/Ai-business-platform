from unittest.mock import patch

from ai_engine import AIQueryEngine


@patch("ai_engine.analytics.get_kpis_for_year")
def test_revenue_for_2024(mock_year):
    mock_year.return_value = {
        "fiscal_year": 2024,
        "period_end": "2024-09-28",
        "revenue": 391035000000,
    }

    result = AIQueryEngine.process_question(
        "What was Apple's revenue in 2024?"
    )

    assert result["status"] == "success"
    assert "391.04 billion" in result["answer"]
    assert result["database"] == "postgresql"


@patch("ai_engine.analytics.compare_years")
def test_compare_revenue_2023_and_2024(mock_compare):
    mock_compare.return_value = {
        "metric": "revenue",
        "year_a": 2023,
        "value_a": 383285000000,
        "year_b": 2024,
        "value_b": 391035000000,
        "change": 7750000000,
        "change_pct": 2.02,
    }

    result = AIQueryEngine.process_question(
        "Compare revenue in 2023 and 2024"
    )

    assert result["status"] == "success"
    assert "383.29 billion" in result["answer"]
    assert "391.04 billion" in result["answer"]
    assert "+2.02%" in result["answer"]


def test_greeting():
    result = AIQueryEngine.process_question("Hello")

    assert result["status"] == "success"
    assert result["answer"]
    assert "greeting" in result.get("intent", "greeting")


@patch("ai_engine.analytics.get_metric_trend")
def test_profitability_trends(mock_trend):
    mock_trend.side_effect = [
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 180000000000}
        ],
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 123000000000}
        ],
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 93736000000}
        ],
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 46.2}
        ],
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 31.5}
        ],
        [
            {"fiscal_year": 2024, "period_end": "2024-09-28", "value": 24.0}
        ],
    ]

    result = AIQueryEngine.process_question(
        "Show the latest profitability trends"
    )

    assert result["status"] == "success"
    assert "gross profit" in result["answer"].lower()
    assert "operating margin" in result["answer"].lower()
    assert "net income" in result["answer"].lower()
    assert mock_trend.call_count == 6


@patch("ai_engine.analytics.get_kpis_for_year")
def test_multiple_metrics_in_one_question(mock_year):
    mock_year.return_value = {
        "fiscal_year": 2024,
        "period_end": "2024-09-28",
        "revenue": 391035000000,
        "net_income": 93736000000,
    }

    result = AIQueryEngine.process_question(
        "Compare revenue and net income in 2024"
    )

    assert result["status"] == "success"
    assert "revenue" in result["answer"].lower()
    assert "net income" in result["answer"].lower()


@patch("ai_engine.analytics.get_best_year")
def test_best_revenue_year(mock_best):
    mock_best.return_value = {
        "fiscal_year": 2025,
        "period_end": "2025-09-27",
        "value": 416161000000,
    }

    result = AIQueryEngine.process_question(
        "Which year had the highest revenue?"
    )

    assert result["status"] == "success"
    assert "2025" in result["answer"]
    assert "416.16 billion" in result["answer"]


@patch("ai_engine.analytics.get_kpis_for_year")
def test_missing_fiscal_year(mock_year):
    mock_year.return_value = None

    result = AIQueryEngine.process_question(
        "What was Apple's revenue in 1900?"
    )

    assert result["status"] == "unavailable"
    assert "1900" in result["answer"]


def test_out_of_scope_question():
    result = AIQueryEngine.process_question(
        "What is the weather today?"
    )

    assert result["status"] == "out_of_scope"
    assert result["answer"]


@patch("ai_engine.analytics.get_kpis_for_year")
def test_percentage_metric_formatting(mock_year):
    mock_year.return_value = {
        "fiscal_year": 2024,
        "period_end": "2024-09-28",
        "net_margin_pct": 24.0,
    }

    result = AIQueryEngine.process_question(
        "What was Apple's net margin in 2024?"
    )

    assert result["status"] == "success"
    assert "24.00%" in result["answer"]


@patch("ai_engine.analytics.get_kpis_for_year")
def test_ratio_metric_formatting(mock_year):
    mock_year.return_value = {
        "fiscal_year": 2024,
        "period_end": "2024-09-28",
        "current_ratio": 0.89,
    }

    result = AIQueryEngine.process_question(
        "What was Apple's current ratio in 2024?"
    )

    assert result["status"] == "success"
    assert "0.89x" in result["answer"]

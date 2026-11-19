import pytest
from unittest.mock import patch

from ai_engine import AIQueryEngine


@patch("ai_engine.analytics.compare_years")
def test_comparison_handles_unavailable_percentage_change(mock_compare):
    mock_compare.return_value = {
        "metric": "revenue",
        "year_a": 2023,
        "value_a": 0,
        "year_b": 2024,
        "value_b": 1000000000,
        "change": 1000000000,
        "change_pct": None,
    }

    result = AIQueryEngine.process_question(
        "Compare revenue in 2023 and 2024"
    )

    assert result["status"] == "success"
    assert "percentage change" in result["answer"].lower() or (
        "not available" in result["answer"].lower()
    )


def test_ambiguous_multi_metric_comparison_requests_clarification():
    result = AIQueryEngine.process_question(
        "Compare Apple's revenue and net income"
    )

    assert result["status"] == "clarification"
    assert "fiscal year" in result["answer"].lower()


@patch("ai_engine.analytics.get_best_year")
def test_best_year_supports_multiple_metrics(mock_best):
    mock_best.side_effect = [
        {
            "fiscal_year": 2025,
            "value": 416161000000,
        },
        {
            "fiscal_year": 2024,
            "value": 93736000000,
        },
    ]

    result = AIQueryEngine.process_question(
        "Which year had the highest revenue and net income?"
    )

    assert result["status"] == "success"
    assert "revenue" in result["answer"].lower()
    assert "net income" in result["answer"].lower()
    assert mock_best.call_count == 2


@patch("ai_engine.analytics.get_kpis_for_year")
def test_top_line_is_recognized_as_revenue(mock_year):
    mock_year.return_value = {
        "fiscal_year": 2024,
        "period_end": "2024-09-28",
        "revenue": 391035000000,
    }

    result = AIQueryEngine.process_question(
        "What was Apple's top-line performance in 2024?"
    )

    assert result["status"] == "success"
    assert "391.04 billion" in result["answer"]

@pytest.mark.parametrize(
    "question",
    [
        "What can you do?",
        "What types of questions can I ask?",
        "Show me examples of questions.",
    ],
)
def test_help_questions_return_supported_examples(question):
    result = AIQueryEngine.process_question(question)

    assert result["status"] == "success"
    assert "revenue" in result["answer"].lower()
    assert "examples" in result["answer"].lower()


def test_apple_privacy_policy_returns_policy_clarification():
    result = AIQueryEngine.process_question(
        "What is Apple's privacy policy?"
    )

    assert result["status"] == "out_of_scope"
    assert "cannot verify" in result["answer"].lower()
    assert "financial" in result["answer"].lower()


import re
from decimal import Decimal

import financial_analytics as analytics


class AIQueryEngine:
    METRICS = {
        "revenue": {
            "column": "revenue",
            "label": "revenue",
            "aliases": [
                "revenue",
                "sales",
                "top line",
                "top-line",
            ],
            "type": "money",
        },
        "net_income": {
            "column": "net_income",
            "label": "net income",
            "aliases": ["net income", "net profit"],
            "type": "money",
        },
        "gross_profit": {
            "column": "gross_profit",
            "label": "gross profit",
            "aliases": ["gross profit"],
            "type": "money",
        },
        "operating_income": {
            "column": "operating_income",
            "label": "operating income",
            "aliases": ["operating income", "operating profit"],
            "type": "money",
        },
        "total_assets": {
            "column": "total_assets",
            "label": "total assets",
            "aliases": ["total assets", "assets"],
            "type": "money",
        },
        "total_liabilities": {
            "column": "total_liabilities",
            "label": "total liabilities",
            "aliases": ["total liabilities", "liabilities"],
            "type": "money",
        },
        "current_assets": {
            "column": "current_assets",
            "label": "current assets",
            "aliases": ["current assets"],
            "type": "money",
        },
        "current_liabilities": {
            "column": "current_liabilities",
            "label": "current liabilities",
            "aliases": ["current liabilities"],
            "type": "money",
        },
        "equity": {
            "column": "equity",
            "label": "equity",
            "aliases": [
                "shareholders equity",
                "shareholder equity",
                "equity",
            ],
            "type": "money",
        },
        "cash": {
            "column": "cash",
            "label": "cash",
            "aliases": ["cash balance", "cash"],
            "type": "money",
        },
        "gross_margin_pct": {
            "column": "gross_margin_pct",
            "label": "gross margin",
            "aliases": ["gross margin"],
            "type": "percentage",
        },
        "operating_margin_pct": {
            "column": "operating_margin_pct",
            "label": "operating margin",
            "aliases": ["operating margin"],
            "type": "percentage",
        },
        "net_margin_pct": {
            "column": "net_margin_pct",
            "label": "net margin",
            "aliases": ["net margin"],
            "type": "percentage",
        },
        "revenue_growth_pct": {
            "column": "revenue_growth_pct",
            "label": "revenue growth",
            "aliases": ["revenue growth", "sales growth"],
            "type": "percentage",
        },
        "net_income_growth_pct": {
            "column": "net_income_growth_pct",
            "label": "net income growth",
            "aliases": ["net income growth", "net profit growth"],
            "type": "percentage",
        },
        "current_ratio": {
            "column": "current_ratio",
            "label": "current ratio",
            "aliases": ["current ratio"],
            "type": "ratio",
        },
        "liabilities_to_equity": {
            "column": "liabilities_to_equity",
            "label": "liabilities to equity ratio",
            "aliases": [
                "liabilities to equity ratio",
                "liabilities to equity",
                "debt to equity ratio",
                "debt-to-equity ratio",
                "debt to equity",
                "debt-to-equity",
            ],
            "type": "ratio",
        },
        "roe_pct": {
            "column": "roe_pct",
            "label": "return on equity",
            "aliases": ["return on equity", "roe"],
            "type": "percentage",
        },
        "roa_pct": {
            "column": "roa_pct",
            "label": "return on assets",
            "aliases": ["return on assets", "roa"],
            "type": "percentage",
        },
    }

    PROFITABILITY_METRICS = [
        "gross_profit",
        "operating_income",
        "net_income",
        "gross_margin_pct",
        "operating_margin_pct",
        "net_margin_pct",
    ]

    @staticmethod
    def _number(value):
        if isinstance(value, Decimal):
            return float(value)
        return value

    @classmethod
    def _format_value(cls, value, metric_key):
        if value is None:
            return "not available"

        value = cls._number(value)
        metric_type = cls.METRICS[metric_key]["type"]

        if metric_type == "money":
            return f"${value / 1_000_000_000:,.2f} billion"

        if metric_type == "percentage":
            return f"{value:,.2f}%"

        if metric_type == "ratio":
            return f"{value:,.2f}x"

        return str(value)

    @classmethod
    def _find_metrics(cls, question):
        question_lower = question.lower()
        found = []

        aliases = []
        for key, details in cls.METRICS.items():
            for alias in details["aliases"]:
                aliases.append((alias, key))

        aliases.sort(key=lambda item: len(item[0]), reverse=True)

        for alias, key in aliases:
            pattern = (
                r"(?<![a-z0-9])"
                + re.escape(alias)
                + r"(?![a-z0-9])"
            )

            if re.search(pattern, question_lower) and key not in found:
                found.append(key)

        return found

    @staticmethod
    def _extract_years(question):
        matches = re.findall(
            r"(?<!\d)(?:FY\s*)?((?:19|20)\d{2})(?!\d)",
            question,
            flags=re.IGNORECASE
          )
        return [int(year) for year in matches]

    @staticmethod
    def _is_greeting(question):
        cleaned = question.lower().strip()

        greetings = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "hi there",
            "hello there",
        }

        return cleaned in greetings

    @staticmethod
    def _is_financial_question(question):
        keywords = [
            "apple",
            "financial",
            "finance",
            "revenue",
            "sales",
            "profit",
            "income",
            "margin",
            "asset",
            "liabilit",
            "equity",
            "cash",
            "ratio",
            "growth",
            "balance sheet",
            "profitability",
            "fiscal year",
            "fy",
            "stock",
            "share",
            "return on",
            "debt",
            "expense",
            "top line",
            "top-line",
        ]

        question_lower = question.lower()

        return any(word in question_lower for word in keywords)

    @staticmethod
    def _result(status, question, answer, intent, tools=None, data=None):
        return {
            "status": status,
            "question": question,
            "answer": answer,
            "intent": intent,
            "database": "postgresql" if tools else None,
            "tools": tools or [],
            "data": data or [],
        }

    @classmethod
    def _format_metric_from_row(cls, row, metric_key):
        details = cls.METRICS[metric_key]
        value = row.get(details["column"])

        return (
            f"{details['label'].title()}: "
            f"{cls._format_value(value, metric_key)}"
        )

    @classmethod
    def _handle_comparison(cls, question, metric_key, years):
        year_a, year_b = years[0], years[1]

        result = analytics.compare_years(
            metric_key,
            year_a,
            year_b,
        )

        if not result:
            return cls._result(
                "unavailable",
                question,
                f"I could not find {cls.METRICS[metric_key]['label']} "
                f"data for both FY{year_a} and FY{year_b}.",
                "comparison",
                ["compare_years"],
            )

        value_a = result.get("value_a")
        value_b = result.get("value_b")
        change = result.get("change")
        change_pct = result.get("change_pct")

        if value_a is None or value_b is None or change is None:
            return cls._result(
                "unavailable",
                question,
                f"The required data for this comparison is incomplete "
                f"for FY{year_a} and FY{year_b}.",
                "comparison",
                ["compare_years"],
                result,
            )

        label = cls.METRICS[metric_key]["label"]
        metric_type = cls.METRICS[metric_key]["type"]

        formatted_a = cls._format_value(value_a, metric_key)
        formatted_b = cls._format_value(value_b, metric_key)

        if metric_type == "money":
            formatted_change = (
                f"${abs(change) / 1_000_000_000:,.2f} billion"
            )
        elif metric_type == "percentage":
            formatted_change = (
                f"{abs(change):,.2f} percentage points"
            )
        else:
            formatted_change = f"{abs(change):,.2f}x"

        direction = "increased" if change >= 0 else "decreased"

        answer = (
            f"Apple's {label} was {formatted_a} in FY{year_a} "
            f"and {formatted_b} in FY{year_b}. "
            f"It {direction} by {formatted_change}."
        )

        if change_pct is None:
            answer += (
                " The percentage change is not available because "
                "the starting value is zero."
            )
        else:
            sign = "+" if change_pct >= 0 else ""
            answer += f" ({sign}{change_pct:,.2f}%)."

        return cls._result(
            "success",
            question,
            answer,
            "comparison",
            ["compare_years"],
            result,
        )

    @classmethod
    def _handle_best_year(cls, question, metric_key):
        result = analytics.get_best_year(metric_key)

        if not result:
            return cls._result(
                "unavailable",
                question,
                f"I could not find available historical "
                f"{cls.METRICS[metric_key]['label']} data.",
                "best_year",
                ["get_best_year"],
            )

        year = result.get("fiscal_year")
        value = result.get("value")
        label = cls.METRICS[metric_key]["label"]

        answer = (
            f"Apple recorded its highest {label} in FY{year}, "
            f"at {cls._format_value(value, metric_key)}."
        )

        return cls._result(
            "success",
            question,
            answer,
            "best_year",
            ["get_best_year"],
            result,
        )

    @classmethod
    def _handle_best_years(cls, question, metric_keys):
        lines = []
        collected_data = []

        for metric_key in metric_keys:
            result = analytics.get_best_year(metric_key)

            if not result:
                lines.append(
                    f"{cls.METRICS[metric_key]['label'].title()}: "
                    "historical data unavailable."
                )
                continue

            year = result.get("fiscal_year")
            value = result.get("value")
            label = cls.METRICS[metric_key]["label"]

            lines.append(
                f"Highest {label}: FY{year}, "
                f"{cls._format_value(value, metric_key)}"
            )

            collected_data.append({
                "metric": metric_key,
                "fiscal_year": year,
                "value": value,
            })

        if not collected_data:
            return cls._result(
                "unavailable",
                question,
                "I could not find historical data for the requested metrics.",
                "best_year",
                ["get_best_year"],
            )

        answer = (
            "Here are Apple's highest recorded values "
            "for the requested metrics:\n"
            + "\n".join(lines)
        )

        return cls._result(
            "success",
            question,
            answer,
            "best_year",
            ["get_best_year"],
            collected_data,
        )

    @classmethod
    def _handle_profitability_trends(cls, question):
        lines = []
        collected_data = []

        for metric_key in cls.PROFITABILITY_METRICS:
            rows = analytics.get_metric_trend(metric_key)

            if not rows:
                continue

            latest = rows[-1]
            value = latest.get("value")
            year = latest.get("fiscal_year")

            label = cls.METRICS[metric_key]["label"]
            formatted = cls._format_value(value, metric_key)

            lines.append(
                f"{label.title()}: {formatted} (FY{year})"
            )

            collected_data.append({
                "metric": metric_key,
                "fiscal_year": year,
                "value": value,
            })

        if not lines:
            return cls._result(
                "unavailable",
                question,
                "I could not find profitability trend data in the "
                "available financial records.",
                "trend",
                ["get_metric_trend"],
            )

        answer = (
            "Here are Apple's latest available profitability figures:\n"
            + "\n".join(lines)
        )

        return cls._result(
            "success",
            question,
            answer,
            "trend",
            ["get_metric_trend"],
            collected_data,
        )

    @classmethod
    def _handle_trend(cls, question, metric_key, years):
        start_year = years[0] if years else None
        end_year = years[-1] if len(years) > 1 else None

        rows = analytics.get_metric_trend(
            metric_key,
            start_year=start_year,
            end_year=end_year,
        )

        if not rows:
            return cls._result(
                "unavailable",
                question,
                f"I could not find historical "
                f"{cls.METRICS[metric_key]['label']} data "
                f"for the requested period.",
                "trend",
                ["get_metric_trend"],
            )

        label = cls.METRICS[metric_key]["label"]

        lines = [
            f"FY{row['fiscal_year']}: "
            f"{cls._format_value(row.get('value'), metric_key)}"
            for row in rows
        ]

        answer = (
            f"Apple's {label} trend:\n"
            + "\n".join(lines)
        )

        return cls._result(
            "success",
            question,
            answer,
            "trend",
            ["get_metric_trend"],
            rows,
        )

    @classmethod
    def _handle_year_query(cls, question, metric_keys, year):
        row = analytics.get_kpis_for_year(year)

        if not row:
            return cls._result(
                "unavailable",
                question,
                f"I could not find financial records for FY{year} "
                f"in the available Apple dataset.",
                "financial_lookup",
                ["get_kpis_for_year"],
            )

        lines = [
            cls._format_metric_from_row(row, metric_key)
            for metric_key in metric_keys
        ]

        answer = (
            f"Apple's FY{year} financial data:\n"
            + "\n".join(lines)
        )

        return cls._result(
            "success",
            question,
            answer,
            "financial_lookup",
            ["get_kpis_for_year"],
            row,
        )

    @classmethod
    def _handle_latest_query(cls, question, metric_keys):
        row = analytics.get_summary()

        if not row:
            return cls._result(
                "unavailable",
                question,
                "I could not retrieve the latest available financial records.",
                "financial_lookup",
                ["get_summary"],
            )

        missing_metrics = [
            key
            for key in metric_keys
            if row.get(cls.METRICS[key]["column"]) is None
        ]

        if missing_metrics:
            all_rows = analytics.get_all_kpis()

            if all_rows:
                row = all_rows[-1]

        year = row.get("fiscal_year", "latest available")

        lines = [
            cls._format_metric_from_row(row, metric_key)
            for metric_key in metric_keys
        ]

        answer = (
            f"Apple's latest available financial data (FY{year}):\n"
            + "\n".join(lines)
        )

        return cls._result(
            "success",
            question,
            answer,
            "financial_lookup",
            ["get_summary", "get_all_kpis"],
            row,
        )

    @classmethod
    def process_question(cls, question):
        question = (question or "").strip()

        if not question:
            return cls._result(
                "error",
                question,
                "Please enter a question.",
                "empty_question",
            )

        if cls._is_greeting(question):
            return cls._result(
                "success",
                question,
                "Hello! I can help you explore Apple's financial data, "
                "including revenue, profitability, assets, liabilities, "
                "financial ratios and year-to-year comparisons. "
                "What would you like to know?",
                "greeting",
            )
                # Handle supported help questions.
        if any(
            phrase in question.lower()
            for phrase in [
                "what can you do",
                "what types of questions can i ask",
                "show me examples of questions",
            ]
        ):
            return cls._result(
                "success",
                question,
                "I can help you explore Apple's financial data. "
                "Here are some examples of questions: "
                "What was Apple's revenue in FY2024? "
                "Compare revenue in FY2023 and FY2024. "
                "What was the highest revenue year?",
                "help",
            )

        # Clarify that Apple's privacy policy is outside this platform's scope.
        if "privacy policy" in question.lower():
            return cls._result(
                "out_of_scope",
                question,
                "I cannot verify Apple's privacy policy using this "
                "platform. I can only help with Apple's financial "
                "data and related financial analysis.",
                "out_of_scope",
            )
        metric_keys = cls._find_metrics(question)
        years = cls._extract_years(question)
        question_lower = question.lower()

        is_profitability_trend = (
            "profitability" in question_lower
            and any(
                word in question_lower
                for word in [
                    "trend",
                    "trends",
                    "historical",
                    "history",
                    "over time",
                ]
            )
        )

        if not metric_keys and not is_profitability_trend:
            if cls._is_financial_question(question):
                return cls._result(
                    "unavailable",
                    question,
                    "I can answer using the available Apple annual "
                    "financial dataset, but I could not identify a "
                    "supported financial metric in your question. "
                    "Try asking about revenue, net income, margins, "
                    "assets, liabilities, cash or financial ratios.",
                    "unsupported_financial_query",
                )

            return cls._result(
                "out_of_scope",
                question,
                "I can help with Apple's annual financial data and "
                "related financial analysis. This question is outside "
                "that scope.",
                "out_of_scope",
            )

        try:
            is_trend = any(
                word in question_lower
                for word in [
                    "trend",
                    "trends",
                    "historical",
                    "history",
                    "over time",
                    "growth over",
                ]
            )

            is_best_year = any(
                word in question_lower
                for word in [
                    "highest",
                    "highest ever",
                    "best year",
                    "maximum",
                    "peak",
                ]
            )

            is_comparison = (
                len(years) >= 2
                or "compare" in question_lower
                or "comparison" in question_lower
            )

            if (
                "profitability" in question_lower
                and is_trend
            ):
                return cls._handle_profitability_trends(question)

            if (
                is_comparison
                and len(metric_keys) > 1
                and len(years) == 0
            ):
                return cls._result(
                    "clarification",
                    question,
                    "Which fiscal years would you like me to compare? "
                    "For example, FY2023 and FY2024. "
                    "I can compare one financial metric at a time.",
                    "comparison",
                )

            if is_best_year and len(metric_keys) > 1:
                return cls._handle_best_years(
                    question,
                    metric_keys,
                )

            if is_best_year and len(metric_keys) == 1:
                return cls._handle_best_year(
                    question,
                    metric_keys[0],
                )

            if is_trend and len(metric_keys) == 1:
                return cls._handle_trend(
                    question,
                    metric_keys[0],
                    years,
                )

            if (
                is_comparison
                and len(years) >= 2
                and len(metric_keys) == 1
            ):
                return cls._handle_comparison(
                    question,
                    metric_keys[0],
                    years,
                )

            if len(years) >= 2 and len(metric_keys) > 1:
                return cls._result(
                    "clarification",
                    question,
                    "Please choose one financial metric for this "
                    "two-year comparison. Which metric would you "
                    "like me to compare?",
                    "comparison",
                )

            if years:
                return cls._handle_year_query(
                    question,
                    metric_keys,
                    years[0],
                )

            return cls._handle_latest_query(
                question,
                metric_keys,
            )

        except Exception as exc:
            print(
                f"AIQueryEngine error: {type(exc).__name__}: {exc}"
            )

            return cls._result(
                "error",
                question,
                "I could not complete that financial query because "
                "the data service encountered an error. Please try again.",
                "financial_query_error",
            )

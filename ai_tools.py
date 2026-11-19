from decimal import Decimal, ROUND_HALF_UP

import financial_analytics as fa

MONEY = {"revenue", "gross_profit", "operating_income", "net_income", "total_assets",
         "total_liabilities", "current_assets", "current_liabilities", "equity", "cash"}
PERCENT = {"gross_margin_pct", "operating_margin_pct", "net_margin_pct",
           "revenue_growth_pct", "net_income_growth_pct", "roe_pct", "roa_pct"}
RATIO = {"current_ratio", "liabilities_to_equity"}


def _round2(x):
    # ROUND_HALF_UP avoids Python's float surprises (e.g. 274.515 -> 274.52)
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _scaled(a, scale):
    return (Decimal(str(a)) / Decimal(scale)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_value(metric, v):
    if v is None:
        return None
    if metric in MONEY:
        sign = "-" if v < 0 else ""
        a = abs(v)
        if a >= 1e9:
            return f"{sign}${_scaled(a, 10**9):,} billion"
        if a >= 1e6:
            return f"{sign}${_scaled(a, 10**6):,} million"
        return f"{sign}${a:,.0f}"
    if metric in PERCENT:
        return f"{_round2(v)}%"
    if metric in RATIO:
        return f"{_round2(v)}"
    return str(v)


def format_change(metric, change):
    if change is None:
        return None
    sign = "+" if change > 0 else ("-" if change < 0 else "")
    mag = format_value(metric, abs(change))
    if metric in PERCENT:
        return f"{sign}{mag[:-1]} percentage points"
    return f"{sign}{mag}"


def add_display(row):
    out = dict(row)
    for key, val in row.items():
        if key in (MONEY | PERCENT | RATIO) and val is not None:
            out[key + "_display"] = format_value(key, val)
    return out


def _years():
    return [r["fiscal_year"] for r in fa.get_all_kpis()]


# ---------------- the tools the AI is allowed to use ----------------

def tool_get_kpis_for_year(fiscal_year):
    row = fa.get_kpis_for_year(int(fiscal_year))
    if row is None:
        return {"error": f"No data for fiscal year {fiscal_year}", "available_years": _years()}
    return add_display(row)


def tool_get_metric_trend(metric, start_year=None, end_year=None):
    points = fa.get_metric_trend(metric, start_year, end_year)
    out = {"metric": metric,
           "points": [{"fiscal_year": p["fiscal_year"], "value": p["value"],
                       "display": format_value(metric, p["value"])} for p in points]}
    if not points:
        out["note"] = "No data for this metric in the requested range"
    return out


def tool_get_best_year(metric):
    row = fa.get_best_year(metric)
    if row is None:
        return {"error": f"No data for metric {metric}"}
    return {"metric": metric, "fiscal_year": row["fiscal_year"], "value": row["value"],
            "display": format_value(metric, row["value"])}


def tool_compare_years(metric, year_a, year_b):
    r = fa.compare_years(metric, int(year_a), int(year_b))
    if r is None:
        return {"error": "One of the years has no data", "available_years": _years()}
    r["display_a"] = format_value(metric, r["value_a"])
    r["display_b"] = format_value(metric, r["value_b"])
    r["change_display"] = format_change(metric, r["change"])
    if r["change_pct"] is not None:
        r["change_pct_display"] = f"{_round2(r['change_pct'])}%"
    return r


def tool_get_summary():
    row = fa.get_summary()
    return add_display(row) if row else {"error": "No data"}


TOOL_FUNCTIONS = {
    "get_kpis_for_year": tool_get_kpis_for_year,
    "get_metric_trend": tool_get_metric_trend,
    "get_best_year": tool_get_best_year,
    "compare_years": tool_compare_years,
    "get_summary": tool_get_summary,
}

_METRIC = {"type": "string", "enum": fa.list_metrics(), "description": "Which metric"}
_YEAR = {"type": "integer", "description": "Fiscal year, e.g. 2024"}

TOOLS = [
    {"name": "get_kpis_for_year",
     "description": "All KPIs (revenue, profit, margins, growth, ratios) for ONE fiscal year.",
     "input_schema": {"type": "object", "properties": {"fiscal_year": _YEAR},
                      "required": ["fiscal_year"]}},
    {"name": "get_metric_trend",
     "description": "One metric across many years, optionally limited to a year range.",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC,
                                     "start_year": _YEAR, "end_year": _YEAR},
                      "required": ["metric"]}},
    {"name": "get_best_year",
     "description": "The fiscal year with the HIGHEST value of a metric.",
     "input_schema": {"type": "object", "properties": {"metric": _METRIC},
                      "required": ["metric"]}},
    {"name": "compare_years",
     "description": "Compare one metric between two fiscal years (change and percent change).",
     "input_schema": {"type": "object",
                      "properties": {"metric": _METRIC, "year_a": _YEAR, "year_b": _YEAR},
                      "required": ["metric", "year_a", "year_b"]}},
    {"name": "get_summary",
     "description": "Headline KPIs for the most recent fiscal year.",
     "input_schema": {"type": "object", "properties": {}}},
]


def run_tool(name, args):
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return func(**(args or {}))
    except ValueError as exc:
        return {"error": str(exc)}
    except TypeError:
        return {"error": "Invalid tool arguments"}
    except Exception as exc:
        print(f"[tool error] {name}: {exc!r}")
        return {"error": "Tool failed"}

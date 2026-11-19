import re
import time

import financial_analytics as fa
from ai_tools import MONEY, run_tool
from audit import log_interaction

MODEL_NAME = "rule-based-router"

LABELS = {
    "revenue": "revenue", "gross_profit": "gross profit",
    "operating_income": "operating income", "net_income": "net income",
    "total_assets": "total assets", "total_liabilities": "total liabilities",
    "current_assets": "current assets", "current_liabilities": "current liabilities",
    "equity": "shareholder equity", "cash": "cash",
    "gross_margin_pct": "gross margin", "operating_margin_pct": "operating margin",
    "net_margin_pct": "net profit margin", "revenue_growth_pct": "revenue growth",
    "net_income_growth_pct": "net income growth", "current_ratio": "current ratio",
    "liabilities_to_equity": "liabilities-to-equity ratio",
    "roe_pct": "return on equity (ROE)", "roa_pct": "return on assets (ROA)",
}

# Words a person might use  ->  the metric name in our database
SYNONYMS = {
    "revenue": ["revenue", "sales", "net sales", "turnover"],
    "net_income": ["net income", "net profit", "profit", "earnings", "income", "bottom line"],
    "gross_profit": ["gross profit"],
    "operating_income": ["operating income", "operating profit"],
    "gross_margin_pct": ["gross margin", "gross profit margin"],
    "operating_margin_pct": ["operating margin"],
    "net_margin_pct": ["net margin", "profit margin", "net profit margin", "net income margin"],
    "revenue_growth_pct": ["revenue growth", "sales growth", "growth rate", "growth"],
    "net_income_growth_pct": ["net income growth", "profit growth", "earnings growth"],
    "current_ratio": ["current ratio", "liquidity"],
    "liabilities_to_equity": ["liabilities to equity", "debt to equity", "leverage", "debt ratio"],
    "roe_pct": ["roe", "return on equity"],
    "roa_pct": ["roa", "return on assets"],
    "total_assets": ["total assets", "assets"],
    "total_liabilities": ["total liabilities", "liabilities"],
    "current_assets": ["current assets"],
    "current_liabilities": ["current liabilities"],
    "equity": ["equity", "shareholder equity", "shareholders equity",
               "stockholders equity", "book value"],
    "cash": ["cash"],
}

# Longest phrase first, so "net profit margin" wins over "profit"
PHRASES = sorted(((p, m) for m, ps in SYNONYMS.items() for p in ps),
                 key=lambda item: -len(item[0]))

GROWTH_VERSION = {"revenue": "revenue_growth_pct", "net_income": "net_income_growth_pct"}

FORECAST = re.compile(r"\b(forecast|predict|prediction|projection|projected|will|future|"
                      r"expected|estimate|going to|next year)\b")
BEST = re.compile(r"\b(best|highest|maximum|max|peak|top|record|largest|biggest|greatest)\b")
WORST = re.compile(r"\b(lowest|worst|minimum|min|smallest|least)\b")
TREND = re.compile(r"\b(trend|over time|history|historical|all years|each year|every year|"
                   r"by year|year by year|across years|over the years|since)\b")
GROW = re.compile(r"\b(grow|grew|growing)\b")
LATEST = re.compile(r"\b(latest|last year|this year|recent|currently)\b")
FIN_WORDS = re.compile(r"\b(apple|apples|financial|financials|kpi|kpis|performance|overview|"
                       r"summary|snapshot|results|numbers|fiscal|fy|company|business|latest)\b")
INJECTION = re.compile(r"ignore (all )?(previous |prior )?instructions|pretend|you are now|"
                       r"system prompt")

OVERVIEW_KEYS = ["revenue", "net_income", "gross_margin_pct", "operating_margin_pct",
                 "net_margin_pct", "revenue_growth_pct", "current_ratio",
                 "liabilities_to_equity", "roe_pct"]


# ---------------- small helpers ----------------

def normalize(question):
    q = question.lower().replace("\u2019", "").replace("'", "").replace("-", " ")
    q = re.sub(r"[^a-z0-9 ]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q.replace("most recent", "latest")


def detect_metric(q):
    for phrase, metric in PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"s?\b", q):
            return metric
    return None


def find_years(q):
    found = []
    for y in re.findall(r"\b(?:19|20)\d{2}\b", q):
        if int(y) not in found:
            found.append(int(y))
    return found


def coverage_text():
    years = [r["fiscal_year"] for r in fa.get_all_kpis()]
    rev = fa.get_metric_trend("revenue")
    out = ""
    if years:
        out += f"Profit and balance-sheet figures exist for fiscal years {min(years)}-{max(years)}. "
    if rev:
        out += (f"Revenue-based figures (revenue, margins, revenue growth) exist only for "
                f"fiscal years {rev[0]['fiscal_year']}-{rev[-1]['fiscal_year']}.")
    return out


def unavailable(label, year):
    return f"Apple's {label} is not available for fiscal year {year}. {coverage_text()}"


def call(name, args, tool_log):
    out = run_tool(name, args)
    tool_log.append({"tool": name, "input": args, "output": out})
    return out


# ---------------- the reasoning ----------------

def _answer(question, tool_log):
    q = normalize(question)
    all_years = [r["fiscal_year"] for r in fa.get_all_kpis()]
    first_year, latest = min(all_years), max(all_years)

    note = ""
    if INJECTION.search(q):
        note = ("I answer only from the verified database, so I cannot change or invent "
                "figures. ")

    metric = detect_metric(q)
    if metric and GROW.search(q):
        metric = GROWTH_VERSION.get(metric, metric)
    years = find_years(q)

    # 1. Forecasts and future years are refused
    if FORECAST.search(q) or any(y > latest for y in years):
        return (note + f"I cannot predict or forecast the future, and my data ends at fiscal "
                f"year {latest}. I can tell you what happened in past years.")

    # 2. Ambiguous margin question
    if metric is None and re.search(r"\bmargins?\b", q):
        return "Which margin do you mean: gross margin, operating margin or net profit margin?"

    # 3. Not about Apple's financial data
    if metric is None and not FIN_WORDS.search(q):
        return (f"I can answer questions about Apple Inc.'s annual financial data from the "
                f"verified database (fiscal years {first_year}-{latest}): revenue, net income, "
                f"margins, growth, current ratio, liabilities-to-equity, ROE/ROA, balance-sheet "
                f"items, the best year for a metric, comparisons between two years, and "
                f"trends. Examples: \"What was net income in 2021?\", "
                f"\"Compare revenue 2022 and 2024\", \"Show the revenue trend\".")

    # 4. Financial question but no specific metric
    if metric is None:
        if len(years) >= 2:
            return (f"Which metric should I compare between {min(years[:2])} and "
                    f"{max(years[:2])}? For example revenue, net income or net profit margin.")
        if BEST.search(q) or WORST.search(q):
            return "Which metric do you mean, for example revenue, net income or a margin?"
        if years:
            row = call("get_kpis_for_year", {"fiscal_year": years[0]}, tool_log)
            if row.get("error"):
                return f"There is no data for fiscal year {years[0]}. {coverage_text()}"
            lines = [f"- {LABELS[k].capitalize()}: {row[k + '_display']}"
                     for k in OVERVIEW_KEYS if row.get(k + "_display")]
            return note + f"Apple's key figures for fiscal year {years[0]}:\n" + "\n".join(lines)
        s = call("get_summary", {}, tool_log)
        lines = [f"- {LABELS[k].capitalize()}: {s[k + '_display']}"
                 for k in OVERVIEW_KEYS if s.get(k + "_display")]
        return note + f"Apple's latest fiscal year is {s['fiscal_year']}:\n" + "\n".join(lines)

    label = LABELS[metric]

    # 5. Highest / lowest year
    if WORST.search(q):
        out = call("get_metric_trend", {"metric": metric}, tool_log)
        points = [p for p in out.get("points", []) if p["value"] is not None]
        if not points:
            return f"Apple's {label} is not available. {coverage_text()}"
        low = min(points, key=lambda p: p["value"])
        return note + (f"Apple's lowest {label} was {low['display']}, in fiscal year "
                       f"{low['fiscal_year']}.")
    if BEST.search(q):
        out = call("get_best_year", {"metric": metric}, tool_log)
        if out.get("error"):
            return f"Apple's {label} is not available. {coverage_text()}"
        return note + (f"Apple's highest {label} was {out['display']}, in fiscal year "
                       f"{out['fiscal_year']}.")

    # 6. Trend over several years
    if TREND.search(q):
        start = end = None
        if len(years) >= 2:
            start, end = min(years[:2]), max(years[:2])
        elif len(years) == 1 and "since" in q:
            start = years[0]
        out = call("get_metric_trend",
                   {"metric": metric, "start_year": start, "end_year": end}, tool_log)
        points = out.get("points", [])
        if not points:
            return f"Apple's {label} is not available for that period. {coverage_text()}"
        lines = [f"FY{p['fiscal_year']}: {p['display']}" for p in points]
        return note + f"Apple's {label} by fiscal year:\n" + "\n".join(lines)

    # 7. Compare two years
    if len(years) >= 2:
        year_a, year_b = sorted(years[:2])
        r = call("compare_years", {"metric": metric, "year_a": year_a, "year_b": year_b},
                 tool_log)
        if r.get("error"):
            return f"There is no data for one of those years. {coverage_text()}"
        missing = [str(y) for y, v in ((year_a, r["value_a"]), (year_b, r["value_b"]))
                   if v is None]
        if missing:
            return unavailable(label, " and ".join(missing))
        text_ = (f"Apple's {label} was {r['display_a']} in FY{year_a} and {r['display_b']} "
                 f"in FY{year_b}, a change of {r['change_display']}")
        if metric in MONEY and r.get("change_pct_display"):
            text_ += f" ({r['change_pct_display']})"
        return note + text_ + "."

    # 8. One metric, one year (default: latest year)
    if years:
        year, assumed = years[0], ""
    else:
        year, assumed = latest, " (the latest fiscal year in the database)"
    row = call("get_kpis_for_year", {"fiscal_year": year}, tool_log)
    if row.get("error"):
        return f"There is no data for fiscal year {year}. {coverage_text()}"
    shown = row.get(metric + "_display")
    if shown is None:
        return unavailable(label, year)
    return note + f"Apple's {label} in fiscal year {year}{assumed} was {shown}."


def ask(question):
    start = time.time()
    tool_log = []
    status = "ok"
    try:
        answer = _answer(question, tool_log)
    except Exception as exc:
        print(f"[error] {exc!r}")
        status = "error"
        answer = "Something went wrong while reading the database. Please try again."
    latency_ms = int((time.time() - start) * 1000)
    log_interaction(question, MODEL_NAME, tool_log, answer, latency_ms, status)
    return {"question": question, "answer": answer, "tool_calls": tool_log,
            "model": MODEL_NAME, "latency_ms": latency_ms, "status": status}

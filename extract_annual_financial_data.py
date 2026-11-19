import json
import pandas as pd
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

RAW_FILE = "data/raw/apple_companyfacts.json"
OUTPUT_FILE = "data/processed/apple_annual_financial_data.csv"


# ============================================================
# METRICS
# ============================================================

METRICS = {
    "assets": "Assets",
    "current_assets": "AssetsCurrent",
    "liabilities": "Liabilities",
    "current_liabilities": "LiabilitiesCurrent",
    "equity": "StockholdersEquity",
    "net_income": "NetIncomeLoss",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "operating_income": "OperatingIncomeLoss",
    "gross_profit": "GrossProfit",
}


# Revenue can appear under different SEC concepts.
# The newer concept is preferred when both represent
# the same reporting period.
REVENUE_CONCEPTS = [
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]


# ============================================================
# HELPERS
# ============================================================

def parse_date(value):
    """Convert SEC date string into Python date."""
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return None


def annual_duration(start, end):
    """
    Check whether a period represents approximately
    one full fiscal year.

    Apple fiscal years can contain 364, 365, or 366 days.
    We use a broad but controlled range to avoid selecting
    quarterly / half-year / nine-month values.
    """

    if start is None or end is None:
        return False

    duration_days = (end - start).days + 1

    return 330 <= duration_days <= 380


# ============================================================
# LOAD SEC COMPANY FACTS
# ============================================================

print("=" * 80)
print("APPLE ANNUAL FINANCIAL DATA EXTRACTION")
print("=" * 80)

print(f"\nLoading raw SEC data:")
print(f"  {RAW_FILE}")

with open(
    RAW_FILE,
    "r",
    encoding="utf-8"
) as f:
    data = json.load(f)


print("Raw SEC data loaded successfully.")


# ============================================================
# READ US-GAAP FACTS
# ============================================================

us_gaap = data.get(
    "facts",
    {}
).get(
    "us-gaap",
    {}
)

if not us_gaap:
    raise RuntimeError(
        "US-GAAP facts were not found in the SEC CompanyFacts file."
    )


print(
    f"US-GAAP concepts available: {len(us_gaap)}"
)


# ============================================================
# STORAGE
# ============================================================

all_records = []


# ============================================================
# PROCESS STANDARD FINANCIAL METRICS
# ============================================================

for metric_name, concept in METRICS.items():

    print("\n" + "-" * 80)
    print(f"Processing: {metric_name}")
    print(f"SEC concept: {concept}")
    print("-" * 80)

    if concept not in us_gaap:

        print(
            f"WARNING: {concept} not found."
        )

        continue

    units = us_gaap[concept].get(
        "units",
        {}
    )

    if "USD" not in units:

        print(
            f"WARNING: USD unit not found for {concept}."
        )

        continue

    metric_records = []

    for item in units["USD"]:

        # ----------------------------------------------------
        # ONLY 10-K
        # ----------------------------------------------------

        if item.get("form") != "10-K":
            continue

        start = parse_date(
            item.get("start")
        )

        end = parse_date(
            item.get("end")
        )

        # ----------------------------------------------------
        # BALANCE SHEET METRICS
        # ----------------------------------------------------
        #
        # Balance-sheet values are point-in-time facts.
        # They normally do not contain a start date.
        # ----------------------------------------------------

        if metric_name in {
            "assets",
            "current_assets",
            "liabilities",
            "current_liabilities",
            "equity",
            "cash",
        }:

            if end is None:
                continue

        # ----------------------------------------------------
        # FLOW METRICS
        # ----------------------------------------------------
        #
        # Income statement metrics must represent a full
        # fiscal year.
        # ----------------------------------------------------

        else:

            if not annual_duration(
                start,
                end
            ):
                continue

        value = item.get("val")

        if value is None:
            continue

        filed = parse_date(
            item.get("filed")
        )

        if filed is None:
            continue

        accession_number = item.get(
            "accn"
        )

        if not accession_number:
            continue

        metric_records.append({

            "metric": metric_name,

            "period_start": start,

            "period_end": end,

            "value": value,

            "filed": filed,

            "frame": item.get("frame"),

            "accession_number": accession_number,

            "source_concept": concept,

        })


    print(
        f"Candidate annual records: "
        f"{len(metric_records)}"
    )


    # ========================================================
    # ORIGINAL-FILING SELECTION
    # ========================================================
    #
    # The same historical period can appear in later SEC
    # filings as a comparative value.
    #
    # Example:
    #
    # FY2024 Assets can appear in:
    #
    #   2024 10-K
    #   2025 10-K as comparative information
    #
    # We want the earliest filing containing the period.
    #
    # Therefore:
    #
    #   period -> earliest filed 10-K
    #
    # This is much safer than keeping the latest filing.
    # ========================================================

    metric_df = pd.DataFrame(
        metric_records
    )

    if metric_df.empty:
        continue


    # Balance-sheet facts are identified by period_end.
    #
    # Flow facts are identified by period_start + period_end.

    if metric_name in {
        "assets",
        "current_assets",
        "liabilities",
        "current_liabilities",
        "equity",
        "cash",
    }:

        duplicate_keys = [
            "period_end"
        ]

    else:

        duplicate_keys = [
            "period_start",
            "period_end"
        ]


    metric_df = metric_df.sort_values(
        by=[
            *duplicate_keys,
            "filed",
            "accession_number",
        ],
        ascending=[
            *([True] * len(duplicate_keys)),
            True,
            True,
        ],
    )


    metric_df = metric_df.drop_duplicates(
        subset=duplicate_keys,
        keep="first"
    )


    print(
        f"Original-period records selected: "
        f"{len(metric_df)}"
    )


    all_records.extend(
        metric_df.to_dict(
            "records"
        )
    )


# ============================================================
# REVENUE
# ============================================================

print("\n" + "=" * 80)
print("PROCESSING: REVENUE")
print("=" * 80)

print("SEC concepts:")

for concept in REVENUE_CONCEPTS:
    print(f"  - {concept}")


revenue_records = []


for concept in REVENUE_CONCEPTS:

    if concept not in us_gaap:

        print(
            f"WARNING: {concept} not found."
        )

        continue

    units = us_gaap[concept].get(
        "units",
        {}
    )

    if "USD" not in units:

        print(
            f"WARNING: USD unit not found for {concept}."
        )

        continue


    for item in units["USD"]:

        # ----------------------------------------------------
        # ONLY 10-K
        # ----------------------------------------------------

        if item.get("form") != "10-K":
            continue


        start = parse_date(
            item.get("start")
        )

        end = parse_date(
            item.get("end")
        )


        # Revenue must represent a full fiscal year.
        if not annual_duration(
            start,
            end
        ):
            continue


        value = item.get("val")

        if value is None:
            continue


        filed = parse_date(
            item.get("filed")
        )

        if filed is None:
            continue


        accession_number = item.get(
            "accn"
        )

        if not accession_number:
            continue


        revenue_records.append({

            "metric": "revenue",

            "period_start": start,

            "period_end": end,

            "value": value,

            "filed": filed,

            "frame": item.get("frame"),

            "accession_number": accession_number,

            "source_concept": concept,

        })


print(
    f"\nRevenue candidates before selection: "
    f"{len(revenue_records)}"
)


# ============================================================
# REVENUE SELECTION
# ============================================================

revenue_df = pd.DataFrame(
    revenue_records
)


if not revenue_df.empty:

    # --------------------------------------------------------
    # Concept priority
    # --------------------------------------------------------
    #
    # If both revenue concepts represent the same period,
    # prefer the newer SEC concept.
    #
    # But filing date remains important:
    # we first want the original filing for the period.
    # --------------------------------------------------------

    revenue_df["concept_priority"] = (
        revenue_df[
            "source_concept"
        ].apply(
            lambda x:
            2
            if x ==
            "RevenueFromContractWithCustomerExcludingAssessedTax"
            else 1
        )
    )


    # --------------------------------------------------------
    # Sort by period first.
    #
    # For the same reporting period:
    #
    # 1. earliest filing
    # 2. preferred revenue concept
    # 3. accession number
    #
    # We intentionally DO NOT keep the latest filing.
    # --------------------------------------------------------

    revenue_df = revenue_df.sort_values(
        by=[
            "period_start",
            "period_end",
            "filed",
            "concept_priority",
            "accession_number",
        ],
        ascending=[
            True,
            True,
            True,
            False,
            True,
        ],
    )


    # --------------------------------------------------------
    # One revenue record per exact annual period.
    #
    # Because the dataframe is sorted by earliest filing first,
    # keep="first" selects the original filing.
    # --------------------------------------------------------

    revenue_df = revenue_df.drop_duplicates(
        subset=[
            "period_start",
            "period_end",
        ],
        keep="first"
    )


    revenue_df = revenue_df.drop(
        columns=[
            "concept_priority"
        ]
    )


    print(
        f"Revenue original-period records selected: "
        f"{len(revenue_df)}"
    )


    all_records.extend(
        revenue_df.to_dict(
            "records"
        )
    )


else:

    print(
        "WARNING: No annual revenue records found."
    )


# ============================================================
# CREATE FINAL DATAFRAME
# ============================================================

print("\n" + "=" * 80)
print("CREATING FINAL DATASET")
print("=" * 80)


df = pd.DataFrame(
    all_records
)


if df.empty:

    raise RuntimeError(
        "No annual financial records were extracted."
    )


# ============================================================
# DATE NORMALIZATION
# ============================================================

df["period_start"] = pd.to_datetime(
    df["period_start"],
    errors="coerce"
)

df["period_end"] = pd.to_datetime(
    df["period_end"],
    errors="coerce"
)

df["filed"] = pd.to_datetime(
    df["filed"],
    errors="coerce"
)


# ============================================================
# FISCAL YEAR
# ============================================================
#
# We derive the reporting fiscal year from period_end.
#
# We intentionally DO NOT use SEC "fy".
#
# Example:
#
# period_end = 2024-09-28
# fiscal_year = 2024
# ============================================================

df["fiscal_year"] = (
    df["period_end"].dt.year
)


# ============================================================
# FINAL DUPLICATE SAFETY CHECK
# ============================================================
#
# This is only a safety layer.
#
# Earlier stages already selected the earliest filing.
#
# Therefore we keep FIRST after sorting by filing date.
# ============================================================

df = df.sort_values(
    by=[
        "metric",
        "period_end",
        "period_start",
        "filed",
        "accession_number",
    ],
    ascending=[
        True,
        True,
        True,
        True,
        True,
    ],
)


df = df.drop_duplicates(
    subset=[
        "metric",
        "period_start",
        "period_end",
    ],
    keep="first"
)


# ============================================================
# FINAL SORT
# ============================================================

df = df.sort_values(
    by=[
        "metric",
        "fiscal_year",
    ]
).reset_index(
    drop=True
)


# ============================================================
# CONVERT DATES TO CSV FORMAT
# ============================================================

df["period_start"] = df[
    "period_start"
].dt.date


df["period_end"] = df[
    "period_end"
].dt.date


df["filed"] = df[
    "filed"
].dt.date


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# FINAL REPORT
# ============================================================

print("\n" + "=" * 80)
print("EXTRACTION COMPLETE")
print("=" * 80)

print(
    f"Output file: {OUTPUT_FILE}"
)

print(
    f"Total records: {len(df)}"
)

print(
    f"Metrics: {df['metric'].nunique()}"
)


print("\nRecords by metric:")

print(
    df["metric"]
    .value_counts()
    .sort_index()
    .to_string()
)


print("\nFiscal-year range:")

print(
    f"  {df['fiscal_year'].min()} "
    f"to "
    f"{df['fiscal_year'].max()}"
)


print("\nRevenue verification:")

revenue_check = df[
    df["metric"] == "revenue"
][
    [
        "fiscal_year",
        "period_start",
        "period_end",
        "value",
        "filed",
        "accession_number",
        "source_concept",
    ]
].sort_values(
    "fiscal_year"
)


if not revenue_check.empty:

    print(
        revenue_check.to_string(
            index=False
        )
    )


print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
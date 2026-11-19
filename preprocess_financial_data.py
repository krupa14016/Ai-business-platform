import json
import pandas as pd
from datetime import datetime


RAW_FILE = "data/raw/apple_companyfacts.json"
OUTPUT_FILE = "data/processed/apple_annual_financial_data.csv"


# ============================================================
# SEC CONCEPTS
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


# Revenue changed SEC concepts over time.
REVENUE_CONCEPTS = [
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def parse_date(value):
    """
    Convert YYYY-MM-DD string to Python date.
    """
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def is_annual_duration(start, end):
    """
    Determine whether a period represents a full fiscal year.

    Apple fiscal years are normally around 364-366 days.
    A 53-week fiscal year can be around 371 days.

    We intentionally allow a wider safe range to avoid
    accidentally removing legitimate annual periods.
    """

    if start is None or end is None:
        return False

    duration_days = (end - start).days + 1

    return 330 <= duration_days <= 380


def is_original_fiscal_year(item, period_end):
    """
    Reject comparative facts appearing in later filings.

    Example:

        period_end = 2022-09-24
        fy = 2022
            -> original FY2022 fact

        period_end = 2022-09-24
        fy = 2023
            -> FY2022 comparative fact appearing
               inside Apple's FY2023 filing

    We only keep the fact when SEC fiscal year matches
    the calendar year of Apple's fiscal period end.
    """

    sec_fy = item.get("fy")

    if sec_fy is None:
        return False

    try:
        sec_fy = int(sec_fy)
    except (TypeError, ValueError):
        return False

    return sec_fy == period_end.year


# ============================================================
# START
# ============================================================

print("=" * 80)
print("APPLE ANNUAL FINANCIAL DATA EXTRACTION")
print("=" * 80)

print("\nLoading SEC CompanyFacts JSON...")

with open(RAW_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

print("SEC data loaded successfully.")

us_gaap = data["facts"]["us-gaap"]

all_records = []


# ============================================================
# NORMAL FINANCIAL METRICS
# ============================================================

for metric_name, concept in METRICS.items():

    print("\n" + "-" * 80)
    print(f"Processing: {metric_name}")
    print(f"SEC concept: {concept}")
    print("-" * 80)

    if concept not in us_gaap:
        print(f"WARNING: {concept} not found.")
        continue

    units = us_gaap[concept]["units"]

    if "USD" not in units:
        print(f"WARNING: USD unit not found for {concept}.")
        continue

    metric_records = []

    total_10k = 0
    comparative_removed = 0
    invalid_periods = 0

    for item in units["USD"]:

        # ----------------------------------------------------
        # ONLY 10-K
        # ----------------------------------------------------

        if item.get("form") != "10-K":
            continue

        total_10k += 1

        start = parse_date(item.get("start"))
        end = parse_date(item.get("end"))

        if end is None:
            invalid_periods += 1
            continue

        # ----------------------------------------------------
        # BALANCE SHEET METRICS
        # ----------------------------------------------------

        if metric_name in [
            "assets",
            "current_assets",
            "liabilities",
            "current_liabilities",
            "equity",
            "cash",
        ]:

            # Balance sheet facts are point-in-time.
            if start is not None:
                continue

            # Reject comparative facts from later fiscal years.
            if not is_original_fiscal_year(item, end):
                comparative_removed += 1
                continue

        # ----------------------------------------------------
        # INCOME STATEMENT METRICS
        # ----------------------------------------------------

        else:

            if start is None or end is None:
                invalid_periods += 1
                continue

            # Must represent a complete fiscal year.
            if not is_annual_duration(start, end):
                invalid_periods += 1
                continue

            # Reject comparative facts from later filings.
            if not is_original_fiscal_year(item, end):
                comparative_removed += 1
                continue

        value = item.get("val")

        if value is None:
            continue

        metric_records.append({
            "metric": metric_name,
            "period_start": start,
            "period_end": end,
            "value": value,
            "filed": item.get("filed"),
            "frame": item.get("frame"),
            "accession_number": item.get("accn"),
            "source_concept": concept,
            "sec_fy": item.get("fy"),
        })

    print(f"10-K records inspected: {total_10k}")
    print(f"Comparative records removed: {comparative_removed}")
    print(f"Invalid/non-annual periods removed: {invalid_periods}")
    print(f"Annual records selected: {len(metric_records)}")

    all_records.extend(metric_records)


# ============================================================
# REVENUE
# ============================================================

print("\n" + "-" * 80)
print("Processing: revenue")
print("SEC concepts:")
print("  - SalesRevenueNet")
print("  - RevenueFromContractWithCustomerExcludingAssessedTax")
print("-" * 80)


revenue_records = []


for concept in REVENUE_CONCEPTS:

    if concept not in us_gaap:
        print(f"WARNING: {concept} not found.")
        continue

    units = us_gaap[concept]["units"]

    if "USD" not in units:
        print(f"WARNING: USD unit not found for {concept}.")
        continue

    for item in units["USD"]:

        # ----------------------------------------------------
        # ONLY 10-K
        # ----------------------------------------------------

        if item.get("form") != "10-K":
            continue

        start = parse_date(item.get("start"))
        end = parse_date(item.get("end"))

        if start is None or end is None:
            continue

        # ----------------------------------------------------
        # FULL FISCAL YEAR ONLY
        # ----------------------------------------------------

        if not is_annual_duration(start, end):
            continue

        # ----------------------------------------------------
        # REMOVE COMPARATIVE FACTS
        # ----------------------------------------------------

        if not is_original_fiscal_year(item, end):
            continue

        value = item.get("val")

        if value is None:
            continue

        revenue_records.append({
            "metric": "revenue",
            "period_start": start,
            "period_end": end,
            "value": value,
            "filed": item.get("filed"),
            "frame": item.get("frame"),
            "accession_number": item.get("accn"),
            "source_concept": concept,
            "sec_fy": item.get("fy"),
        })


print(
    f"Revenue records before concept deduplication: "
    f"{len(revenue_records)}"
)


# ============================================================
# REVENUE DEDUPLICATION
# ============================================================

revenue_df = pd.DataFrame(revenue_records)

if not revenue_df.empty:

    revenue_df["period_end"] = pd.to_datetime(
        revenue_df["period_end"]
    )

    revenue_df["period_start"] = pd.to_datetime(
        revenue_df["period_start"]
    )

    revenue_df["filed"] = pd.to_datetime(
        revenue_df["filed"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Prefer the newer revenue concept.
    # --------------------------------------------------------

    revenue_df["concept_priority"] = revenue_df[
        "source_concept"
    ].apply(
        lambda x:
        2
        if x == "RevenueFromContractWithCustomerExcludingAssessedTax"
        else 1
    )

    # Sort so preferred concept is first.
    revenue_df = revenue_df.sort_values(
        by=[
            "period_end",
            "concept_priority",
            "filed",
        ],
        ascending=[
            True,
            False,
            True,
        ],
    )

    # --------------------------------------------------------
    # One revenue record per fiscal period.
    # --------------------------------------------------------

    revenue_df = revenue_df.drop_duplicates(
        subset=[
            "period_start",
            "period_end",
        ],
        keep="first",
    )

    revenue_df = revenue_df.drop(
        columns=["concept_priority"]
    )

    revenue_df["period_start"] = (
        revenue_df["period_start"].dt.date
    )

    revenue_df["period_end"] = (
        revenue_df["period_end"].dt.date
    )

    revenue_df["filed"] = (
        revenue_df["filed"].dt.date
    )

    all_records.extend(
        revenue_df.to_dict("records")
    )


print(
    f"Revenue records after concept deduplication: "
    f"{len(revenue_df)}"
)


# ============================================================
# CREATE FINAL DATAFRAME
# ============================================================

print("\n" + "=" * 80)
print("CREATING FINAL DATASET")
print("=" * 80)

df = pd.DataFrame(all_records)


if df.empty:
    raise RuntimeError(
        "No annual financial records were extracted."
    )


# ============================================================
# DATE CONVERSION
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
# We derive Apple's reporting fiscal year from period_end.
#
# Example:
#
# period_end = 2024-09-28
# fiscal_year = 2024
#
# This is intentional.
# We do NOT blindly use SEC "fy" as our final reporting
# year because SEC filing metadata can contain comparative
# facts.
# ============================================================

df["fiscal_year"] = (
    df["period_end"].dt.year
)


# ============================================================
# FINAL DUPLICATE PROTECTION
# ============================================================

# At this stage comparative records should already be gone.
#
# If multiple records still exist for the same metric and
# period, prefer the earliest filing because that corresponds
# to the original fiscal-year filing rather than a later
# comparative filing.

df = df.sort_values(
    by=[
        "metric",
        "period_end",
        "filed",
    ],
    ascending=[
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
    keep="first",
)


# ============================================================
# FINAL SORT
# ============================================================

df = df.sort_values(
    by=[
        "metric",
        "fiscal_year",
    ]
).reset_index(drop=True)


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)

print(f"\nTotal records: {len(df)}")

print(
    f"Total metrics: "
    f"{df['metric'].nunique()}"
)

print("\nRecords by metric:")

print(
    df["metric"]
    .value_counts()
    .sort_index()
)


# ============================================================
# REVENUE CHECK
# ============================================================

print("\n" + "=" * 80)
print("REVENUE VALIDATION")
print("=" * 80)

revenue_check = (
    df[df["metric"] == "revenue"]
    [
        [
            "fiscal_year",
            "period_start",
            "period_end",
            "value",
            "filed",
            "sec_fy",
            "source_concept",
        ]
    ]
    .sort_values("fiscal_year")
)

print(
    revenue_check.to_string(
        index=False
    )
)


# ============================================================
# DUPLICATE CHECK
# ============================================================

duplicate_check = (
    df.groupby(
        [
            "metric",
            "period_start",
            "period_end",
        ]
    )
    .size()
)

duplicates = duplicate_check[
    duplicate_check > 1
]

print("\nDuplicate annual periods remaining:")

print(len(duplicates))


# ============================================================
# FINAL VALIDATION
# ============================================================

print("\n" + "=" * 80)
print("FINAL VALIDATION")
print("=" * 80)

# Every selected record must have a fiscal year matching
# period_end year.

year_mismatch = df[
    df["fiscal_year"]
    != df["period_end"].dt.year
]

print(
    f"Fiscal-year mismatches: "
    f"{len(year_mismatch)}"
)

# Check for negative values.

negative_values = df[
    df["value"] < 0
]

print(
    f"Negative values: "
    f"{len(negative_values)}"
)

# Check duplicate metric/period combinations.

print(
    f"Duplicate metric-period combinations: "
    f"{len(duplicates)}"
)


if (
    len(year_mismatch) == 0
    and len(negative_values) == 0
    and len(duplicates) == 0
):
    print("\nSTATUS: PASS")
else:
    print("\nSTATUS: REVIEW REQUIRED")


print("\nSaved to:")
print(OUTPUT_FILE)

print("\nAnnual financial extraction completed.")

print("=" * 80)
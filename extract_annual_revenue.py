import json
import pandas as pd
from datetime import datetime


# ============================================================
# FILE PATHS
# ============================================================

RAW_FILE = "data/raw/apple_companyfacts.json"
OUTPUT_FILE = "data/processed/apple_annual_revenue.csv"


# ============================================================
# REVENUE CONCEPTS
# ============================================================

# Older Apple filings
OLD_CONCEPT = "SalesRevenueNet"

# Newer Apple filings
NEW_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


# ============================================================
# HELPER FUNCTION
# ============================================================

def parse_date(value):
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%d").date()


# ============================================================
# LOAD SEC DATA
# ============================================================

print("=" * 80)
print("APPLE ANNUAL REVENUE EXTRACTION")
print("=" * 80)

print("\nLoading SEC companyfacts JSON...")

with open(RAW_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)

print("SEC data loaded successfully.")


# ============================================================
# GET US-GAAP FACTS
# ============================================================

us_gaap = data["facts"]["us-gaap"]


# ============================================================
# EXTRACT RECORDS
# ============================================================

records = []


def extract_concept(concept, source_name):

    if concept not in us_gaap:
        print(f"\nWARNING: {concept} not found.")
        return

    units = us_gaap[concept]["units"]

    if "USD" not in units:
        print(f"\nWARNING: USD unit not found for {concept}.")
        return

    for item in units["USD"]:

        # Only 10-K filings
        if item.get("form") != "10-K":
            continue

        start = parse_date(item.get("start"))
        end = parse_date(item.get("end"))

        # Revenue must have both dates
        if start is None or end is None:
            continue

        # Calculate period length
        duration_days = (end - start).days + 1

        # Keep only full-year periods
        if duration_days < 300:
            continue

        records.append({
            "source_concept": source_name,
            "period_start": start,
            "period_end": end,
            "duration_days": duration_days,
            "value": item.get("val"),
            "filed": item.get("filed"),
            "frame": item.get("frame"),
            "accession_number": item.get("accn")
        })


# ============================================================
# EXTRACT BOTH REVENUE CONCEPTS
# ============================================================

print("\nExtracting old revenue concept...")

extract_concept(
    OLD_CONCEPT,
    "SalesRevenueNet"
)

print("Extracting new revenue concept...")

extract_concept(
    NEW_CONCEPT,
    "RevenueFromContractWithCustomerExcludingAssessedTax"
)


# ============================================================
# CREATE DATAFRAME
# ============================================================

df = pd.DataFrame(records)

if df.empty:
    print("\nERROR: No revenue records found.")
    exit()


# ============================================================
# SORT
# ============================================================

df = df.sort_values(
    by=["period_end", "filed", "source_concept"]
).reset_index(drop=True)


# ============================================================
# REMOVE DUPLICATE HISTORICAL FILINGS
# ============================================================

# The same fiscal period can appear in multiple later filings.
#
# Example:
#
# 2019 revenue may appear in:
# 2019 filing
# 2020 filing
# 2021 filing
#
# We keep the earliest filing containing that period.

df = df.sort_values(
    by=["period_end", "filed"]
)

df = df.drop_duplicates(
    subset=["period_start", "period_end"],
    keep="first"
)


# ============================================================
# HANDLE THE 2017 CONCEPT TRANSITION
# ============================================================

# Both concepts contain Apple's FY2017 revenue:
#
# SalesRevenueNet = 229.234B
# RevenueFromContract... = 229.234B
#
# We keep only one copy of that period.

df = df.sort_values(
    by=["period_end", "source_concept"]
)

df = df.drop_duplicates(
    subset=["period_start", "period_end"],
    keep="first"
)


# ============================================================
# CREATE FISCAL YEAR
# ============================================================

# Apple's fiscal year ends around September.
# Therefore, the fiscal year is determined from period_end.

df["fiscal_year"] = df["period_end"].apply(
    lambda x: x.year
)


# ============================================================
# FINAL SORT
# ============================================================

df = df.sort_values(
    by="fiscal_year"
).reset_index(drop=True)


# ============================================================
# SELECT FINAL COLUMNS
# ============================================================

df = df[
    [
        "fiscal_year",
        "period_start",
        "period_end",
        "duration_days",
        "value",
        "source_concept",
        "filed",
        "frame",
        "accession_number"
    ]
]


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# DISPLAY RESULT
# ============================================================

print("\n" + "=" * 80)
print("FINAL ANNUAL REVENUE DATA")
print("=" * 80)

print(
    df[
        [
            "fiscal_year",
            "period_start",
            "period_end",
            "duration_days",
            "value",
            "source_concept"
        ]
    ].to_string(index=False)
)

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"Total annual revenue records: {len(df)}")

print(f"\nSaved to:")
print(OUTPUT_FILE)

print("\nExtraction completed successfully.")
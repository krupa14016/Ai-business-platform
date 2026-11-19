
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------
# 1. File paths
# ---------------------------------------------------------
INPUT_FILE = Path("data/processed/apple_financial_data_clean.csv")
OUTPUT_FILE = Path("data/processed/apple_financial_data_final.csv")

print("=" * 70)
print("APPLE FINANCIAL DATA - FINAL CLEANING")
print("=" * 70)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input CSV not found: {INPUT_FILE.resolve()}\n"
        "Run this script from your AI-BI platform project folder."
    )

df = pd.read_csv(INPUT_FILE)
print(f"\nOriginal rows: {len(df)}")
print(f"Original columns: {len(df.columns)}")

# ---------------------------------------------------------
# 2. Check required columns
# ---------------------------------------------------------
required_columns = [
    "company_name",
    "cik",
    "metric",
    "period_start",
    "period_end",
    "duration_days",
    "fiscal_year",
    "fiscal_period",
    "value",
    "unit",
    "form",
    "filing_date",
]

missing_columns = [c for c in required_columns if c not in df.columns]

if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")

# ---------------------------------------------------------
# 3. Convert dates and numeric columns safely
# ---------------------------------------------------------
for col in ["period_start", "period_end", "filing_date"]:
    df[col] = pd.to_datetime(df[col], errors="coerce")

df["value"] = pd.to_numeric(df["value"], errors="coerce")
df["duration_days"] = pd.to_numeric(
    df["duration_days"], errors="coerce"
)

# A missing start date is allowed for point-in-time metrics.
# A missing end date is not acceptable for this dataset.
bad_end_dates = df["period_end"].isna().sum()

if bad_end_dates:
    raise ValueError(
        f"{bad_end_dates} rows have missing/invalid period_end dates. "
        "Fix these source records before continuing."
    )

bad_values = df["value"].isna().sum()

if bad_values:
    raise ValueError(
        f"{bad_values} rows have missing/non-numeric financial values. "
        "Inspect these records before continuing."
    )

# ---------------------------------------------------------
# 4. Recalculate duration only when both dates are present
# ---------------------------------------------------------
has_both_dates = df["period_start"].notna() & df["period_end"].notna()

df.loc[has_both_dates, "duration_days"] = (
    df.loc[has_both_dates, "period_end"]
    - df.loc[has_both_dates, "period_start"]
).dt.days + 1

# Point-in-time facts have no period duration.
df.loc[df["period_start"].isna(), "duration_days"] = pd.NA

# Start date must not be later than end date.
bad_date_order = (
    df["period_start"].notna()
    & (df["period_start"] > df["period_end"])
)

if bad_date_order.any():
    print("\nRows with start dates after end dates:")
    print(
        df.loc[
            bad_date_order,
            ["metric", "period_start", "period_end", "value"]
        ].to_string(index=False)
    )
    raise ValueError("Invalid reporting date order detected.")

# ---------------------------------------------------------
# 5. Correct Apple's fiscal year
# ---------------------------------------------------------
# Apple's fiscal year generally ends in September.
# Period ends in October-December belong to the next fiscal year.
end_year = df["period_end"].dt.year
end_month = df["period_end"].dt.month

df["fiscal_year"] = end_year + end_month.ge(10).astype(int)
df["fiscal_year"] = df["fiscal_year"].astype("Int64")

# ---------------------------------------------------------
# 6. Correct fiscal-period labels where they can be inferred
# ---------------------------------------------------------
# Annual duration -> FY
# Nine-month cumulative duration -> Q3
# Six-month cumulative duration -> Q2
# Single-quarter duration -> Q1/Q2/Q3/Q4
# Point-in-time facts -> quarter/year-end based on end month

month_to_instant_period = {
    12: "Q1",
    3: "Q2",
    6: "Q3",
    9: "FY",
}

month_to_quarter_period = {
    12: "Q1",
    3: "Q2",
    6: "Q3",
    9: "Q4",
}

duration = df["duration_days"]
end_month = df["period_end"].dt.month

# Preserve the original label for durations that do not fit
# a recognizable reporting-period pattern.
new_period = df["fiscal_period"].copy()

new_period.loc[duration.between(350, 380)] = "FY"
new_period.loc[duration.between(250, 290)] = "Q3"
new_period.loc[duration.between(160, 200)] = "Q2"

single_quarter = duration.between(70, 110)
for month, label in month_to_quarter_period.items():
    new_period.loc[single_quarter & (end_month == month)] = label

instant = duration.isna()
for month, label in month_to_instant_period.items():
    new_period.loc[instant & (end_month == month)] = label

df["fiscal_period"] = new_period

# ---------------------------------------------------------
# 7. Identify duplicate reporting periods correctly
# ---------------------------------------------------------
# Duration-based facts use start + end dates.
# Instant facts have no start date, so their period is identified
# by the end date. pandas treats missing start dates as the same
# value when duplicated() is used with this subset.
dedup_keys = [
    "company_name",
    "cik",
    "metric",
    "period_start",
    "period_end",
    "unit",
]

duplicate_rows_before = int(
    df.duplicated(subset=dedup_keys, keep=False).sum()
)

duplicate_groups_before = int(
    df.duplicated(subset=dedup_keys, keep="first").sum()
)

print("\nDuplicate-period check before cleaning:")
print("Rows belonging to repeated period groups:", duplicate_rows_before)
print("Extra rows in repeated period groups:", duplicate_groups_before)

# ---------------------------------------------------------
# 8. Choose one record for each metric and reporting period
# ---------------------------------------------------------
# Preference:
# - Annual duration: 10-K, then 10-Q, then 8-K
# - September point-in-time balance: 10-K, then 10-Q, then 8-K
# - Other interim periods: 10-Q, then 10-K, then 8-K
#
# Within the same preference, the latest filing is selected.
# 8-K rows are retained if they are the only available record.

form = df["form"].fillna("").astype(str).str.upper().str.strip()
is_instant = df["duration_days"].isna()
is_annual_duration = df["duration_days"].between(350, 380)
is_september_instant = is_instant & (df["period_end"].dt.month == 9)

df["_form_rank"] = 3

annual_or_year_end = is_annual_duration | is_september_instant

df.loc[annual_or_year_end & (form == "10-K"), "_form_rank"] = 0
df.loc[annual_or_year_end & (form == "10-Q"), "_form_rank"] = 1
df.loc[annual_or_year_end & (form == "8-K"), "_form_rank"] = 2

interim = ~annual_or_year_end

df.loc[interim & (form == "10-Q"), "_form_rank"] = 0
df.loc[interim & (form == "10-K"), "_form_rank"] = 1
df.loc[interim & (form == "8-K"), "_form_rank"] = 2

# Sort by preference first, then latest filing date.
df = df.sort_values(
    by=["_form_rank", "filing_date"],
    ascending=[True, False],
    na_position="last",
)

before_deduplication = len(df)

df = df.drop_duplicates(
    subset=dedup_keys,
    keep="first",
).copy()

df = df.drop(columns=["_form_rank"])
df = df.sort_values(
    by=["metric", "period_end", "period_start"],
    na_position="first",
).reset_index(drop=True)

print("\nDeduplication results:")
print("Rows before deduplication:", before_deduplication)
print("Rows removed:", before_deduplication - len(df))
print("Rows after deduplication:", len(df))

# ---------------------------------------------------------
# 9. Format dates and save a NEW CSV
# ---------------------------------------------------------
for col in ["period_start", "period_end", "filing_date"]:
    df[col] = df[col].dt.strftime("%Y-%m-%d")

# Keep missing start dates blank; they are valid for instant facts.
df.to_csv(OUTPUT_FILE, index=False)

print("\nSaved cleaned file:")
print(OUTPUT_FILE.resolve())

# ---------------------------------------------------------
# 10. Validate the final output
# ---------------------------------------------------------
check = pd.read_csv(OUTPUT_FILE)

remaining_duplicate_rows = int(
    check.duplicated(subset=dedup_keys, keep=False).sum()
)

missing_values = int(
    pd.to_numeric(check["value"], errors="coerce").isna().sum()
)

missing_fiscal_year = int(
    pd.to_numeric(check["fiscal_year"], errors="coerce").isna().sum()
)

invalid_end_dates = int(
    pd.to_datetime(check["period_end"], errors="coerce").isna().sum()
)

print("\n" + "=" * 70)
print("FINAL VALIDATION")
print("=" * 70)
print("Final row count:", len(check))
print("Duplicate metric-period rows:", remaining_duplicate_rows)
print("Missing/non-numeric financial values:", missing_values)
print("Missing fiscal years:", missing_fiscal_year)
print("Missing/invalid period_end dates:", invalid_end_dates)

print("\nRows by metric:")
print(check["metric"].value_counts().to_string())

final_duration = pd.to_numeric(check["duration_days"], errors="coerce")
annual_revenue = check[
    check["metric"].astype(str).str.lower().eq("revenue")
    & final_duration.between(350, 380)
]

print("\nAnnual-length revenue records after cleaning:")
print("Count:", len(annual_revenue))
if not annual_revenue.empty:
    print(
        annual_revenue[
            ["period_start", "period_end", "fiscal_year", "value", "form"]
        ].sort_values("period_end").to_string(index=False)
    )

if (
    remaining_duplicate_rows == 0
    and missing_values == 0
    and missing_fiscal_year == 0
    and invalid_end_dates == 0
):
    print("\nBASIC CLEANING VALIDATION PASSED")
    print("Review the annual revenue records before database loading.")
else:
    print("\nVALIDATION FAILED - DO NOT LOAD INTO POSTGRESQL YET.")

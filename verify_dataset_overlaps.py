import pandas as pd
from pathlib import Path

BASE = Path("data/processed")

FILES = {
    "annual": BASE / "apple_financial_data_annual.csv",
    "quarterly": BASE / "apple_financial_data_quarterly.csv",
    "snapshots": BASE / "apple_balance_sheet_snapshots.csv",
}

KEYS = [
    "metric",
    "period_start",
    "period_end",
    "fiscal_year",
    "fiscal_period",
    "accession_number",
]

REQUIRED = [
    "company_name",
    "cik",
    "metric",
    "sec_concept",
    "period_start",
    "period_end",
    "fiscal_year",
    "fiscal_period",
    "value",
    "unit",
    "accession_number",
    "record_type",
]

def normalize_key_columns(df):
    # Read keys consistently as strings; preserve blank dates as blanks.
    for col in KEYS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df

def report_duplicates(df, keys, label):
    count = int(df.duplicated(subset=keys, keep=False).sum())
    print(f"{label}: {count}")
    return count

print("=" * 70)
print("CHECKPOINT 1: FILES EXIST")
print("=" * 70)

for name, path in FILES.items():
    print(f"{name}: {'FOUND' if path.exists() else 'MISSING'} - {path}")

if not all(path.exists() for path in FILES.values()):
    raise FileNotFoundError("One or more required CSV files are missing.")

# Read columns as strings to avoid inconsistent merge-key types.
annual = pd.read_csv(FILES["annual"], dtype=str, keep_default_na=False)
quarterly = pd.read_csv(FILES["quarterly"], dtype=str, keep_default_na=False)
snapshots = pd.read_csv(FILES["snapshots"], dtype=str, keep_default_na=False)

datasets = {
    "annual": annual,
    "quarterly": quarterly,
    "snapshots": snapshots,
}

print("\n" + "=" * 70)
print("CHECKPOINT 2: ROW COUNTS AND COLUMN STRUCTURE")
print("=" * 70)

for name, df in datasets.items():
    print(f"\n{name.upper()}")
    print("Rows:", len(df))
    print("Columns:", len(df.columns))
    print("Missing required columns:", [c for c in REQUIRED if c not in df.columns])

if any(any(c not in df.columns for c in REQUIRED) for df in datasets.values()):
    raise ValueError("A dataset is missing required columns. Stop and inspect the output.")

print("\nColumn lists identical across all files:",
      len(set(tuple(df.columns) for df in datasets.values())) == 1)

print("\n" + "=" * 70)
print("CHECKPOINT 3: RECORD TYPES")
print("=" * 70)

for name, df in datasets.items():
    print(f"\n{name.upper()}")
    print(df["record_type"].value_counts(dropna=False).to_string())

annual_balance = annual[annual["record_type"] == "balance_snapshot"].copy()
annual_flow = annual[annual["record_type"] == "annual_flow"].copy()

print("\nAnnual flow rows:", len(annual_flow))
print("Annual balance snapshot rows:", len(annual_balance))
print("Quarterly rows:", len(quarterly))
print("Dedicated balance snapshot rows:", len(snapshots))

print("\n" + "=" * 70)
print("CHECKPOINT 4: OVERLAP BETWEEN ANNUAL AND SNAPSHOT FILES")
print("=" * 70)

annual_balance = normalize_key_columns(annual_balance)
snapshots = normalize_key_columns(snapshots)

comparison = annual_balance.merge(
    snapshots,
    on=KEYS,
    how="outer",
    suffixes=("_annual", "_snapshot"),
    indicator=True
)

shared = comparison[comparison["_merge"] == "both"].copy()
annual_only = comparison[comparison["_merge"] == "left_only"]
snapshot_only = comparison[comparison["_merge"] == "right_only"]

print("Annual balance records:", len(annual_balance))
print("Dedicated snapshot records:", len(snapshots))
print("Matching keys:", len(shared))
print("Annual-only keys:", len(annual_only))
print("Snapshot-only keys:", len(snapshot_only))

if len(shared):
    annual_values = pd.to_numeric(shared["value_annual"], errors="coerce")
    snapshot_values = pd.to_numeric(shared["value_snapshot"], errors="coerce")
    value_mismatch = ~(
        annual_values.eq(snapshot_values)
        | (annual_values.isna() & snapshot_values.isna())
    )

    concept_mismatch = (
        shared["sec_concept_annual"].fillna("")
        != shared["sec_concept_snapshot"].fillna("")
    )

    print("Matching keys with different values:", int(value_mismatch.sum()))
    print("Matching keys with different SEC concepts:", int(concept_mismatch.sum()))

    if value_mismatch.any():
        print("\nSample value mismatches:")
        print(shared.loc[value_mismatch, [
            "metric", "period_end", "value_annual", "value_snapshot"
        ]].head(10).to_string(index=False))

    if concept_mismatch.any():
        print("\nSample concept mismatches:")
        print(shared.loc[concept_mismatch, [
            "metric", "period_end",
            "sec_concept_annual", "sec_concept_snapshot"
        ]].head(10).to_string(index=False))

print("\n" + "=" * 70)
print("CHECKPOINT 5: REQUIRED-FIELD AND NUMERIC VALIDATION")
print("=" * 70)

for name, df in datasets.items():
    print(f"\n{name.upper()}")
    for col in ["metric", "period_end", "value", "record_type", "cik"]:
        blank_count = int(df[col].astype(str).str.strip().eq("").sum())
        print(f"Blank {col}: {blank_count}")

    numeric_values = pd.to_numeric(df["value"], errors="coerce")
    print("Values that are not numeric:", int(numeric_values.isna().sum()))
    print("Invalid fiscal years:", int(
        pd.to_numeric(df["fiscal_year"], errors="coerce").isna().sum()
    ))

    # Blank period_start is allowed for point-in-time balance snapshots.
    start_blank = int(df["period_start"].astype(str).str.strip().eq("").sum())
    print("Blank period_start (inspect by record type):", start_blank)

print("\n" + "=" * 70)
print("CHECKPOINT 6: DUPLICATES IN EACH SOURCE")
print("=" * 70)

for name, df in datasets.items():
    print(f"\n{name.upper()}")
    print("Exact duplicate rows:", int(df.duplicated().sum()))

    df_keys = normalize_key_columns(df.copy())
    report_duplicates(df_keys, KEYS, "Rows involved in candidate-key duplicates")

print("\n" + "=" * 70)
print("CHECKPOINT 7: PROPOSED CANONICAL DATASET")
print("=" * 70)

# Do not append annual balance snapshots here: they are compared against
# the dedicated snapshot file above to avoid double-counting.
canonical = pd.concat(
    [annual_flow, quarterly, snapshots],
    ignore_index=True,
    sort=False
)

print("Annual flow rows:", len(annual_flow))
print("Quarterly flow rows:", len(quarterly))
print("Dedicated snapshot rows:", len(snapshots))
print("Total proposed rows:", len(canonical))
print("Exact duplicate rows:", int(canonical.duplicated().sum()))

canonical_keys = normalize_key_columns(canonical.copy())
report_duplicates(
    canonical_keys,
    KEYS,
    "Rows involved in candidate-key duplicates"
)

stronger_keys = [
    "cik", "metric", "sec_concept", "period_start", "period_end",
    "fiscal_year", "fiscal_period", "accession_number", "unit", "record_type"
]
for col in stronger_keys:
    canonical_keys[col] = canonical_keys[col].fillna("").astype(str).str.strip()

report_duplicates(
    canonical_keys,
    stronger_keys,
    "Rows involved in stronger-key duplicates"
)

print("\nRows per canonical record type:")
print(canonical["record_type"].value_counts(dropna=False).to_string())

print("\n" + "=" * 70)
print("CHECKPOINT 8: DATE AND COMPANY CONSISTENCY")
print("=" * 70)

for name, df in datasets.items():
    end_dates = pd.to_datetime(df["period_end"], errors="coerce")
    print(f"{name}: invalid period_end dates =", int(end_dates.isna().sum()))

    ciks = sorted(set(df["cik"].astype(str).str.strip()) - {""})
    print(f"{name}: CIK values =", ciks)

print("\n" + "=" * 70)
print("CHECKPOINT 9: SAFETY SUMMARY")
print("=" * 70)

print("Proposed canonical row count:", len(canonical))
print("No database records were changed by this script.")
print("Do not run a PostgreSQL loader until the output is reviewed.")
print("Review overlap mismatches and candidate-key duplicates before loading.")

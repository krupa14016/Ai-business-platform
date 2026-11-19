
import pandas as pd
from pathlib import Path

INPUT_FILE = Path("data/processed/apple_financial_data_clean.csv")

REQUIRED_COLUMNS = [
    "metric",
    "period_start",
    "period_end",
    "value",
    "filed",
    "frame",
    "accession_number",
    "source_concept",
    "fiscal_year",
]

print("=" * 65)
print("APPLE FINANCIAL DATA VALIDATION")
print("=" * 65)

# 1. Confirm the input file exists
if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"File not found: {INPUT_FILE.resolve()}"
    )

# 2. Load the cleaned dataset
df = pd.read_csv(INPUT_FILE)

print(f"\nFile: {INPUT_FILE.resolve()}")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

# 3. Check required columns
missing_columns = [
    col for col in REQUIRED_COLUMNS
    if col not in df.columns
]

if missing_columns:
    print("\nFAIL: Missing columns:", missing_columns)
    raise SystemExit("Fix the columns before continuing.")

print("\nPASS: All required columns are present.")

# 4. Check missing values in essential columns
essential = ["metric", "period_end", "value", "fiscal_year"]
missing_counts = df[essential].isnull().sum()

print("\nMissing values in essential columns:")
print(missing_counts.to_string())

null_fail = missing_counts.sum() > 0

# 5. Ensure financial values are numeric
df["value"] = pd.to_numeric(df["value"], errors="coerce")
invalid_values = int(df["value"].isna().sum())

print(f"\nInvalid or missing numeric values: {invalid_values}")

# 6. Check fiscal years
df["fiscal_year"] = pd.to_numeric(
    df["fiscal_year"], errors="coerce"
)

invalid_years = int(df["fiscal_year"].isna().sum())

print(f"Missing or invalid fiscal years: {invalid_years}")

# 7. Check duplicate metric/year combinations
duplicate_mask = df.duplicated(
    subset=["metric", "fiscal_year"],
    keep=False
)

duplicates = df.loc[
    duplicate_mask,
    ["metric", "fiscal_year", "value",
     "period_end", "source_concept", "filed"]
].sort_values(["metric", "fiscal_year", "filed"])

print(f"\nRows involved in duplicate metric/year pairs: {len(duplicates)}")

if not duplicates.empty:
    print("\nFirst 20 duplicate rows:")
    print(duplicates.head(20).to_string(index=False))
else:
    print("PASS: No duplicate metric/year pairs.")

# 8. Check the dataset's year range and metric counts
valid_years = df["fiscal_year"].dropna()

if not valid_years.empty:
    print(
        f"\nFiscal year range: "
        f"{int(valid_years.min())}–{int(valid_years.max())}"
    )

print("\nRows per metric:")
print(df["metric"].value_counts().sort_index().to_string())

# 9. Check revenue specifically
revenue = df[df["metric"].astype(str).str.lower() == "revenue"].copy()
revenue = revenue.sort_values("fiscal_year")

print(f"\nRevenue records: {len(revenue)}")

if not revenue.empty:
    print(
        f"Revenue year range: "
        f"{int(revenue['fiscal_year'].min())}–"
        f"{int(revenue['fiscal_year'].max())}"
    )

    print("\nRevenue by fiscal year:")
    print(
        revenue[["fiscal_year", "value", "source_concept"]]
        .to_string(index=False)
    )
else:
    print("WARNING: No rows use the metric name 'revenue'.")

# 10. Final result
has_duplicate_pairs = not duplicates.empty
has_invalid_values = invalid_values > 0
has_invalid_years = invalid_years > 0

print("\n" + "=" * 65)

if (
    not null_fail
    and not has_duplicate_pairs
    and not has_invalid_values
    and not has_invalid_years
):
    print("PASS: Basic structural validation succeeded.")
    print("Next: verify source facts, then proceed to PostgreSQL.")
else:
    print("FAIL: Do not load this dataset into PostgreSQL yet.")
    print("Resolve the issues listed above first.")

print("=" * 65)

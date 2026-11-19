import pandas as pd

FILE_PATH = "data/processed/apple_financial_data_clean.csv"

df = pd.read_csv(FILE_PATH)

print()
print("=" * 70)
print("AI-BI DATA QUALITY REPORT")
print("=" * 70)


print()
print("DATASET SIZE")
print("-" * 70)

print("Rows:", len(df))
print("Columns:", len(df.columns))


# ============================================================
# COMPANY
# ============================================================

print()
print("COMPANY")
print("-" * 70)

print(df["company_name"].unique())


# ============================================================
# METRICS
# ============================================================

print()
print("METRICS")
print("-" * 70)

print(df["metric"].value_counts())


# ============================================================
# FORMS
# ============================================================

print()
print("SEC FORMS")
print("-" * 70)

print(df["form"].value_counts())


# ============================================================
# UNITS
# ============================================================

print()
print("UNITS")
print("-" * 70)

print(df["unit"].value_counts())


# ============================================================
# MISSING VALUES
# ============================================================

print()
print("MISSING VALUES")
print("-" * 70)

missing = df.isna().sum()

print(
    missing[
        missing > 0
    ]
)

print()
print("DUPLICATES")
print("-" * 70)

print(
    "Exact duplicate rows:",
    df.duplicated().sum()
)


# ============================================================
# DATE RANGE
# ============================================================

print()
print("DATE RANGE")
print("-" * 70)

print(
    "Earliest:",
    df["period_end"].min()
)

print(
    "Latest:",
    df["period_end"].max()
)

print()
print("NEGATIVE VALUES")
print("-" * 70)

negative_values = (
    df["value"] < 0
).sum()

print(
    "Number of negative financial values:",
    negative_values
)

print()
print("=" * 70)
print("DATA QUALITY CHECK COMPLETED")
print("=" * 70)
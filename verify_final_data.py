
import pandas as pd

path = "data/processed/apple_financial_data_final.csv"
df = pd.read_csv(path)

print("=" * 65)
print("FINAL DATASET VERIFICATION")
print("=" * 65)

print("\n1. Records by metric and fiscal period:")
print(pd.crosstab(df["metric"], df["fiscal_period"], dropna=False).to_string())

print("\n2. Records by metric and SEC form:")
print(pd.crosstab(df["metric"], df["form"], dropna=False).to_string())

print("\n3. Annual records by metric:")
df["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce")
annual = df[df["duration_days"].between(350, 380)]

print(annual.groupby("metric").size().to_string())

print("\n4. Revenue records by reporting duration:")
revenue = df[df["metric"].str.lower() == "revenue"].copy()
print(
    revenue[
        ["period_start", "period_end", "duration_days",
         "fiscal_year", "fiscal_period", "value", "form"]
    ].sort_values(["period_end", "period_start"]).to_string(index=False)
)

print("\n5. Duplicate reporting periods:")
keys = [
    "company_name", "cik", "metric",
    "period_start", "period_end", "unit"
]
print("Duplicate rows:", df.duplicated(subset=keys, keep=False).sum())

print("\n6. Date and value checks:")
print("Missing period_end:", df["period_end"].isna().sum())
print("Missing values:", df["value"].isna().sum())
print("Missing fiscal_year:", df["fiscal_year"].isna().sum())

print("\nVerification report finished.")

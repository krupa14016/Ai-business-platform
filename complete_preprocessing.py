
from pathlib import Path
import pandas as pd

# ============================================================
# APPLE FINANCIAL DATA: FINAL PREPROCESSING + QUALITY CHECKS
# ============================================================

BASE = Path("data/processed")
SOURCE = BASE / "apple_financial_data_final.csv"

ANNUAL_OUT = BASE / "apple_financial_data_annual.csv"
QUARTERLY_OUT = BASE / "apple_financial_data_quarterly.csv"
BALANCE_OUT = BASE / "apple_balance_sheet_snapshots.csv"

FLOW_METRICS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
]

BALANCE_METRICS = [
    "assets",
    "current_assets",
    "current_liabilities",
    "liabilities",
    "cash",
    "equity",
]

print("=" * 72)
print("APPLE FINANCIAL DATA - FINAL PREPROCESSING")
print("=" * 72)

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Source file not found: {SOURCE.resolve()}\n"
        "Run this script from your AI-BI platform project folder."
    )

df = pd.read_csv(SOURCE)

required = [
    "company_name", "cik", "metric", "period_start", "period_end",
    "duration_days", "fiscal_year", "fiscal_period", "value", "unit",
    "form", "filing_date", "sec_concept", "accession_number", "frame",
]
missing_cols = [c for c in required if c not in df.columns]

if missing_cols:
    raise ValueError(f"Missing required columns: {missing_cols}")

print("\n[1/8] SOURCE FILE")
print("File:", SOURCE.resolve())
print("Rows:", len(df))
print("Columns:", len(df.columns))

# Convert types safely.
for col in ["period_start", "period_end", "filing_date"]:
    df[col] = pd.to_datetime(df[col], errors="coerce")

df["value"] = pd.to_numeric(df["value"], errors="coerce")
df["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce")
df["metric"] = df["metric"].astype(str).str.strip().str.lower()
df["form"] = df["form"].fillna("").astype(str).str.upper().str.strip()

# Required values.
if df["period_end"].isna().any():
    raise ValueError(
        f"{df['period_end'].isna().sum()} records have invalid period_end dates."
    )

if df["value"].isna().any():
    raise ValueError(
        f"{df['value'].isna().sum()} records have missing/non-numeric values."
    )

# Recalculate duration only for facts that have both start and end dates.
has_dates = df["period_start"].notna() & df["period_end"].notna()
df.loc[has_dates, "duration_days"] = (
    df.loc[has_dates, "period_end"] -
    df.loc[has_dates, "period_start"]
).dt.days + 1

bad_order = (
    df["period_start"].notna()
    & (df["period_start"] > df["period_end"])
)
if bad_order.any():
    raise ValueError(f"{int(bad_order.sum())} records have invalid date order.")

# Apple's fiscal year normally ends in September.
# October-December period ends belong to the following fiscal year.
end_year = df["period_end"].dt.year
end_month = df["period_end"].dt.month
df["fiscal_year"] = (
    end_year + end_month.ge(10).astype(int)
).astype("Int64")

# Normalize reporting periods for flow metrics based on the period end.
month_to_quarter = {12: "Q1", 3: "Q2", 6: "Q3", 9: "Q4"}
for month, quarter in month_to_quarter.items():
    mask = (
        df["metric"].isin(FLOW_METRICS)
        & df["duration_days"].between(70, 110)
        & (df["period_end"].dt.month == month)
    )
    df.loc[mask, "fiscal_period"] = quarter

df.loc[
    df["metric"].isin(FLOW_METRICS)
    & df["duration_days"].between(350, 380),
    "fiscal_period",
] = "FY"

# ============================================================
# Helper: select one preferred source fact per business key.
# ============================================================

def choose_one(frame, keys, annual=False):
    frame = frame.copy()

    if frame.empty:
        return frame

    form_rank = {"10-K": 0, "10-Q": 1, "8-K": 2}

    if not annual:
        # For individual quarters, prefer 10-Q; use 10-K if necessary.
        form_rank = {"10-Q": 0, "10-K": 1, "8-K": 2}

    frame["_rank"] = frame["form"].map(form_rank).fillna(3)

    frame = frame.sort_values(
        ["_rank", "filing_date"],
        ascending=[True, False],
        na_position="last",
    )

    frame = frame.drop_duplicates(subset=keys, keep="first")
    return frame.drop(columns=["_rank"]).copy()


# ============================================================
# [2/8] Create annual flow records.
# Annual flow values are full-year totals, not quarterly totals.
# ============================================================

flow = df[df["metric"].isin(FLOW_METRICS)].copy()

annual_flow = flow[
    flow["duration_days"].between(350, 380)
].copy()

annual_flow = choose_one(
    annual_flow,
    ["metric", "fiscal_year"],
    annual=True,
)
annual_flow["record_type"] = "annual_flow"
annual_flow["is_derived"] = False

print("\n[2/8] ANNUAL FLOW RECORDS")
print(annual_flow.groupby("metric").size().to_string())

# ============================================================
# [3/8] Create individual-quarter flow records.
# Exclude 6-month, 9-month and annual cumulative totals.
# ============================================================

quarter_candidates = flow[
    flow["duration_days"].between(70, 110)
    & flow["period_start"].notna()
].copy()

quarter_candidates = choose_one(
    quarter_candidates,
    ["metric", "fiscal_year", "fiscal_period"],
    annual=False,
)

quarter_candidates["record_type"] = "quarter_flow"
quarter_candidates["is_derived"] = False

print("\n[3/8] INDIVIDUAL-QUARTER FLOW RECORDS BEFORE Q4 FILL")
print(quarter_candidates.groupby(["metric", "fiscal_period"]).size().to_string())

# ============================================================
# [4/8] Derive missing Q4 only when safe.
# Q4 = annual total - Q1 - Q2 - Q3.
# Requires one Q1, Q2, Q3 and an annual total for that metric/year.
# ============================================================

quarterly = quarter_candidates.copy()
derived_rows = []

annual_lookup = {
    (str(row["metric"]), int(row["fiscal_year"])): row
    for _, row in annual_flow.iterrows()
    if pd.notna(row["fiscal_year"])
}

for (metric, year), annual_row in annual_lookup.items():
    group = quarterly[
        (quarterly["metric"] == metric)
        & (quarterly["fiscal_year"] == year)
    ]

    periods = group["fiscal_period"].tolist()

    # If Q4 already exists, do not replace it.
    if "Q4" in periods:
        continue

    # Only derive Q4 when all three individual quarters exist.
    if not all(q in periods for q in ["Q1", "Q2", "Q3"]):
        continue

    q_values = {}
    for q in ["Q1", "Q2", "Q3"]:
        values = group.loc[group["fiscal_period"] == q, "value"]
        if len(values) != 1:
            q_values = {}
            break
        q_values[q] = float(values.iloc[0])

    if len(q_values) != 3:
        continue

    q4_value = (
        float(annual_row["value"])
        - q_values["Q1"]
        - q_values["Q2"]
        - q_values["Q3"]
    )

    if q4_value < 0:
        print(
            f"WARNING: Skipped derived Q4 for {metric}, FY{year}: "
            f"calculated value is negative ({q4_value})."
        )
        continue

    q3_end = pd.to_datetime(
        group.loc[group["fiscal_period"] == "Q3", "period_end"].iloc[0]
    )
    annual_end = pd.to_datetime(annual_row["period_end"])
    q4_start = q3_end + pd.Timedelta(days=1)

    if q4_start > annual_end:
        print(
            f"WARNING: Skipped derived Q4 for {metric}, FY{year}: "
            "quarter dates are inconsistent."
        )
        continue

    new_row = annual_row.to_dict()
    new_row.update({
        "period_start": q4_start,
        "period_end": annual_end,
        "duration_days": (annual_end - q4_start).days + 1,
        "fiscal_period": "Q4",
        "value": q4_value,
        "form": "DERIVED",
        "sec_concept": "DERIVED_Q4_FROM_ANNUAL_MINUS_Q1_Q2_Q3",
        "accession_number": pd.NA,
        "frame": pd.NA,
        "record_type": "quarter_flow",
        "is_derived": True,
    })
    derived_rows.append(new_row)

if derived_rows:
    quarterly = pd.concat(
        [quarterly, pd.DataFrame(derived_rows)],
        ignore_index=True,
    )

quarterly["fiscal_year"] = pd.to_numeric(
    quarterly["fiscal_year"], errors="raise"
).astype("Int64")

quarterly = quarterly.sort_values(
    ["metric", "fiscal_year", "fiscal_period"]
).reset_index(drop=True)

print("\nDerived Q4 records:", len(derived_rows))
print("Quarterly flow records after Q4 processing:", len(quarterly))

# ============================================================
# [5/8] Create balance-sheet snapshots.
# These are point-in-time balances, not quarterly flow totals.
# ============================================================

balance = df[
    df["metric"].isin(BALANCE_METRICS)
    & df["duration_days"].isna()
].copy()

# For point-in-time facts, label snapshots by the ending month.
month_to_snapshot = {
    12: "Q1",
    3: "Q2",
    6: "Q3",
    9: "FY",
}

for month, label in month_to_snapshot.items():
    mask = balance["period_end"].dt.month == month
    balance.loc[mask, "fiscal_period"] = label

balance = balance[
    balance["fiscal_period"].isin(["Q1", "Q2", "Q3", "FY"])
].copy()


# Prefer 10-K for fiscal-year-end balances.
# Prefer 10-Q for interim quarter-end balances.
balance["_rank"] = 3

year_end = balance["fiscal_period"].eq("FY")

balance.loc[year_end & balance["form"].eq("10-K"), "_rank"] = 0
balance.loc[year_end & balance["form"].eq("10-Q"), "_rank"] = 1
balance.loc[year_end & balance["form"].eq("8-K"), "_rank"] = 2

interim = ~year_end

balance.loc[interim & balance["form"].eq("10-Q"), "_rank"] = 0
balance.loc[interim & balance["form"].eq("10-K"), "_rank"] = 1
balance.loc[interim & balance["form"].eq("8-K"), "_rank"] = 2

balance = balance.sort_values(
    ["_rank", "filing_date"],
    ascending=[True, False],
    na_position="last",
)

balance = balance.drop_duplicates(
    subset=["metric", "fiscal_year", "fiscal_period"],
    keep="first",
).drop(columns=["_rank"]).copy()


balance["record_type"] = "balance_snapshot"
balance["is_derived"] = False

print("\n[5/8] BALANCE-SHEET SNAPSHOTS")
print(balance.groupby(["metric", "fiscal_period"]).size().to_string())

# Annual dataset: annual flow totals + FY-end balance-sheet snapshots.
annual_balance = balance[balance["fiscal_period"] == "FY"].copy()
annual = pd.concat(
    [annual_flow, annual_balance],
    ignore_index=True,
)
annual = annual.sort_values(
    ["metric", "fiscal_year"]
).reset_index(drop=True)

# ============================================================
# [6/8] Reconciliation: Q1 + Q2 + Q3 + Q4 versus annual total.
# ============================================================

quarterly_lookup = {
    (str(row["metric"]), int(row["fiscal_year"]), str(row["fiscal_period"])):
        float(row["value"])
    for _, row in quarterly.iterrows()
    if pd.notna(row["fiscal_year"])
}

reconciliation = []

for _, annual_row in annual_flow.iterrows():
    metric = str(annual_row["metric"])
    year = int(annual_row["fiscal_year"])
    q_keys = [(metric, year, q) for q in ["Q1", "Q2", "Q3", "Q4"]]

    if not all(key in quarterly_lookup for key in q_keys):
        continue

    quarter_sum = sum(quarterly_lookup[key] for key in q_keys)
    annual_value = float(annual_row["value"])
    difference = quarter_sum - annual_value
    tolerance = max(1.0, abs(annual_value) * 0.000001)

    reconciliation.append({
        "metric": metric,
        "fiscal_year": year,
        "annual_value": annual_value,
        "quarter_sum": quarter_sum,
        "difference": difference,
        "within_tolerance": abs(difference) <= tolerance,
    })

recon = pd.DataFrame(reconciliation)

print("\n[6/8] ANNUAL-TO-QUARTERLY RECONCILIATION")
if recon.empty:
    print("No complete annual + Q1-Q4 groups available to reconcile.")
    print("This is a coverage limitation, not automatically a failure.")
else:
    print(recon.to_string(index=False))
    print("Groups checked:", len(recon))
    print("Groups outside tolerance:", int((~recon["within_tolerance"]).sum()))

# ============================================================
# [7/8] Save output datasets without overwriting source facts.
# ============================================================

BASE.mkdir(parents=True, exist_ok=True)

def prepare_for_csv(frame):
    frame = frame.copy()
    for col in ["period_start", "period_end", "filing_date"]:
        if col in frame.columns:
            frame[col] = pd.to_datetime(
                frame[col], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
    return frame

prepare_for_csv(annual).to_csv(ANNUAL_OUT, index=False)
prepare_for_csv(quarterly).to_csv(QUARTERLY_OUT, index=False)
prepare_for_csv(balance).to_csv(BALANCE_OUT, index=False)

print("\n[7/8] OUTPUT FILES")
print("Annual dataset:", ANNUAL_OUT.resolve())
print("Quarterly flow dataset:", QUARTERLY_OUT.resolve())
print("Balance-sheet snapshots:", BALANCE_OUT.resolve())

# ============================================================
# [8/8] Reload and validate the saved files.
# ============================================================

annual_check = pd.read_csv(ANNUAL_OUT)
quarterly_check = pd.read_csv(QUARTERLY_OUT)
balance_check = pd.read_csv(BALANCE_OUT)

annual_dup = int(
    annual_check.duplicated(
        subset=["metric", "fiscal_year"]
    ).sum()
)

quarter_dup = int(
    quarterly_check.duplicated(
        subset=["metric", "fiscal_year", "fiscal_period"]
    ).sum()
)

balance_dup = int(
    balance_check.duplicated(
        subset=["metric", "fiscal_year", "fiscal_period"]
    ).sum()
)

invalid_values = sum([
    pd.to_numeric(annual_check["value"], errors="coerce").isna().sum(),
    pd.to_numeric(quarterly_check["value"], errors="coerce").isna().sum(),
    pd.to_numeric(balance_check["value"], errors="coerce").isna().sum(),
])

invalid_annual_years = int(
    pd.to_numeric(annual_check["fiscal_year"], errors="coerce").isna().sum()
)
invalid_quarter_years = int(
    pd.to_numeric(quarterly_check["fiscal_year"], errors="coerce").isna().sum()
)
invalid_balance_years = int(
    pd.to_numeric(balance_check["fiscal_year"], errors="coerce").isna().sum()
)

recon_failures = (
    0 if recon.empty else int((~recon["within_tolerance"]).sum())
)

print("\n[8/8] FINAL QUALITY CHECKS")
print("Annual rows:", len(annual_check))
print("Quarterly flow rows:", len(quarterly_check))
print("Balance snapshot rows:", len(balance_check))
print("Duplicate annual metric/year keys:", annual_dup)
print("Duplicate quarterly metric/year/period keys:", quarter_dup)
print("Duplicate balance snapshot keys:", balance_dup)
print("Missing/non-numeric values across outputs:", int(invalid_values))
print(
    "Missing fiscal years across outputs:",
    invalid_annual_years + invalid_quarter_years + invalid_balance_years,
)

print("\nQuarterly flow rows by metric and quarter:")
if not quarterly_check.empty:
    print(
        quarterly_check.groupby(
            ["metric", "fiscal_period"]
        ).size().to_string()
    )

if (
    annual_dup == 0
    and quarter_dup == 0
    and balance_dup == 0
    and invalid_values == 0
    and invalid_annual_years + invalid_quarter_years + invalid_balance_years == 0
    and recon_failures == 0
):
    print("\nSTATUS: STRUCTURAL CHECKS PASSED")
    print("Review data coverage and source values before PostgreSQL loading.")
else:
    print("\nSTATUS: REVIEW REQUIRED")
    print("Do not load the analytical datasets until flagged issues are resolved.")

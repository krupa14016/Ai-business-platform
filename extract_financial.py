import json
import pandas as pd
from datetime import datetime


# ============================================================
# FILE PATHS
# ============================================================

RAW_FILE = "data/raw/apple_companyfacts.json"

OUTPUT_FILE = "data/processed/apple_financial_data.csv"


# ============================================================
# FINANCIAL METRICS
# ============================================================

METRICS = {
    "assets": "Assets",
    "current_assets": "AssetsCurrent",
    "liabilities": "Liabilities",
    "current_liabilities": "LiabilitiesCurrent",
    "equity": "StockholdersEquity",
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "net_income": "NetIncomeLoss",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "operating_income": "OperatingIncomeLoss",
    "gross_profit": "GrossProfit",
}


# ============================================================
# DATE FUNCTION
# ============================================================

def parse_date(value):

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return None


# ============================================================
# START
# ============================================================

print("=" * 80)
print("APPLE FINANCIAL DATA EXTRACTION")
print("=" * 80)


# ============================================================
# LOAD SEC JSON
# ============================================================

print("\nLoading SEC CompanyFacts JSON...")

with open(
    RAW_FILE,
    "r",
    encoding="utf-8"
) as file:

    data = json.load(file)

print("SEC data loaded successfully.")


# ============================================================
# GET US GAAP DATA
# ============================================================

us_gaap = data["facts"]["us-gaap"]


# ============================================================
# STORAGE
# ============================================================

records = []


# ============================================================
# EXTRACT ONE METRIC
# ============================================================

def extract_metric(metric_name, concept):

    print("\n" + "-" * 80)
    print(f"Processing: {metric_name}")
    print(f"SEC concept: {concept}")
    print("-" * 80)

    if concept not in us_gaap:

        print(
            f"WARNING: SEC concept '{concept}' was not found."
        )

        return


    units = us_gaap[concept]["units"]


    # --------------------------------------------------------
    # Find the appropriate unit
    # --------------------------------------------------------

    if "USD" in units:

        unit_name = "USD"

    elif "USD/shares" in units:

        unit_name = "USD/shares"

    else:

        print(
            f"WARNING: No supported unit found for {concept}."
        )

        return


    count = 0


    # --------------------------------------------------------
    # Read every SEC record
    # --------------------------------------------------------

    for item in units[unit_name]:

        form = item.get("form")

        start = parse_date(
            item.get("start")
        )

        end = parse_date(
            item.get("end")
        )


        # ----------------------------------------------------
        # Balance-sheet metrics
        #
        # These normally have only an end date.
        # ----------------------------------------------------

        if start is None and end is None:

            continue


        # ----------------------------------------------------
        # Determine duration
        # ----------------------------------------------------

        if start is not None and end is not None:

            duration_days = (
                end - start
            ).days + 1

        else:

            duration_days = None


        # ----------------------------------------------------
        # Keep only useful SEC filings
        # ----------------------------------------------------

        if form not in [
            "10-K",
            "10-Q",
            "8-K"
        ]:

            continue


        # ----------------------------------------------------
        # Create record
        # ----------------------------------------------------

        records.append({

            "company_name":
                data.get(
                    "entityName",
                    "Apple Inc."
                ),

            "cik":
                data.get(
                    "cik",
                    "0000320193"
                ),

            "metric":
                metric_name,

            "sec_concept":
                concept,

            "period_start":
                start,

            "period_end":
                end,

            "duration_days":
                duration_days,

            "fiscal_year":
                item.get("fy"),

            "fiscal_period":
                item.get("fp"),

            "value":
                item.get("val"),

            "unit":
                unit_name,

            "form":
                form,

            "filing_date":
                parse_date(
                    item.get("filed")
                ),

            "accession_number":
                item.get("accn"),

            "frame":
                item.get("frame")

        })

        count += 1


    print(
        f"Records extracted: {count}"
    )


# ============================================================
# EXTRACT ALL METRICS
# ============================================================

for metric_name, concept in METRICS.items():

    extract_metric(
        metric_name,
        concept
    )


# ============================================================
# CREATE DATAFRAME
# ============================================================

print("\n" + "=" * 80)
print("CREATING DATAFRAME")
print("=" * 80)

df = pd.DataFrame(records)


# ============================================================
# CHECK EMPTY DATA
# ============================================================

if df.empty:

    print(
        "\nERROR: No financial records were extracted."
    )

    exit()


# ============================================================
# SORT DATA
# ============================================================

df = df.sort_values(
    by=[
        "metric",
        "period_end",
        "filing_date"
    ]
)


# ============================================================
# SAVE CSV
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("EXTRACTION SUMMARY")
print("=" * 80)

print(
    f"\nTotal records: {len(df)}"
)

print(
    f"\nTotal metrics: {df['metric'].nunique()}"
)

print("\nRecords by metric:")

print(
    df["metric"].value_counts()
)


print("\n" + "=" * 80)
print("OUTPUT")
print("=" * 80)

print(
    f"\nSaved to:"
)

print(
    OUTPUT_FILE
)

print("\nExtraction completed successfully.")

print("=" * 80)
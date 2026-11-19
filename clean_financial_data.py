import pandas as pd
import os
import sys


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "data/processed/apple_financial_data.csv"
OUTPUT_FILE = "data/processed/apple_financial_data_clean.csv"


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "company_name",
    "cik",
    "metric",
    "sec_concept",
    "period_start",
    "period_end",
    "duration_days",
    "fiscal_year",
    "fiscal_period",
    "value",
    "unit",
    "form",
    "filing_date",
    "accession_number",
    "frame",
]


# ============================================================
# MAIN CLEANING FUNCTION
# ============================================================

def main():

    print()
    print("=" * 70)
    print("APPLE FINANCIAL DATA CLEANING")
    print("=" * 70)

    # --------------------------------------------------------
    # STEP 1: CHECK INPUT FILE
    # --------------------------------------------------------

    print()
    print("STEP 1: CHECKING INPUT FILE")
    print("-" * 70)

    if not os.path.exists(INPUT_FILE):
        print("ERROR: Input file was not found.")
        print()
        print("Expected:")
        print(INPUT_FILE)
        sys.exit(1)

    print("Input file found:")
    print(INPUT_FILE)

    # --------------------------------------------------------
    # STEP 2: LOAD DATA
    # --------------------------------------------------------

    print()
    print("STEP 2: LOADING FINANCIAL DATA")
    print("-" * 70)

    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as error:
        print("ERROR while reading CSV:")
        print(error)
        sys.exit(1)

    print("Rows loaded:", len(df))
    print("Columns loaded:", len(df.columns))

    print()
    print("Columns:")
    for column in df.columns:
        print("-", column)

    # --------------------------------------------------------
    # STEP 3: CHECK REQUIRED COLUMNS
    # --------------------------------------------------------

    print()
    print("STEP 3: CHECKING REQUIRED COLUMNS")
    print("-" * 70)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        print("ERROR: Required columns are missing:")

        for column in missing_columns:
            print("-", column)

        print()
        print("Cleaning stopped.")
        sys.exit(1)

    print("All required columns are present.")

    # --------------------------------------------------------
    # STEP 4: KEEP EXPECTED COLUMNS
    # --------------------------------------------------------

    print()
    print("STEP 4: STANDARDIZING COLUMN STRUCTURE")
    print("-" * 70)

    # Keep the complete SEC metadata structure.
    df = df[REQUIRED_COLUMNS].copy()

    print("Final column structure prepared.")
    print("Columns:", len(df.columns))

    # --------------------------------------------------------
    # STEP 5: CONVERT DATA TYPES
    # --------------------------------------------------------

    print()
    print("STEP 5: CONVERTING DATA TYPES")
    print("-" * 70)

    date_columns = [
        "period_start",
        "period_end",
        "filing_date",
    ]

    for column in date_columns:
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce"
        )

    numeric_columns = [
        "cik",
        "duration_days",
        "fiscal_year",
        "value",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    print("Date columns converted:")
    for column in date_columns:
        print("-", column)

    print()
    print("Numeric columns converted:")
    for column in numeric_columns:
        print("-", column)

    # --------------------------------------------------------
    # STEP 6: STANDARDIZE TEXT
    # --------------------------------------------------------

    print()
    print("STEP 6: STANDARDIZING TEXT DATA")
    print("-" * 70)

    text_columns = [
        "company_name",
        "metric",
        "sec_concept",
        "fiscal_period",
        "unit",
        "form",
        "accession_number",
        "frame",
    ]

    for column in text_columns:

        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
        )

    print("Text fields standardized.")

    # --------------------------------------------------------
    # STEP 7: CHECK EXACT DUPLICATES
    # --------------------------------------------------------

    print()
    print("STEP 7: CHECKING EXACT DUPLICATES")
    print("-" * 70)

    rows_before_duplicates = len(df)

    exact_duplicates = df.duplicated().sum()

    print(
        "Exact duplicate rows found:",
        exact_duplicates
    )

    # Remove only completely identical records.
    df = df.drop_duplicates()

    rows_after_duplicates = len(df)

    duplicates_removed = (
        rows_before_duplicates
        - rows_after_duplicates
    )

    print("Rows before:", rows_before_duplicates)
    print("Rows after:", rows_after_duplicates)
    print(
        "Exact duplicates removed:",
        duplicates_removed
    )

    # --------------------------------------------------------
    # STEP 8: CHECK MISSING VALUES
    # --------------------------------------------------------

    print()
    print("STEP 8: CHECKING MISSING VALUES")
    print("-" * 70)

    missing_values = df.isna().sum()

    has_missing_values = False

    for column, count in missing_values.items():

        if count > 0:

            has_missing_values = True

            print(
                f"{column}: {count}"
            )

    if not has_missing_values:
        print("No missing values found.")

    # --------------------------------------------------------
    # STEP 9: CHECK CRITICAL FIELDS
    # --------------------------------------------------------

    print()
    print("STEP 9: CHECKING CRITICAL FINANCIAL FIELDS")
    print("-" * 70)

    critical_columns = [
        "company_name",
        "metric",
        "period_end",
        "value",
        "filing_date",
    ]

    print("Missing values in critical fields:")

    for column in critical_columns:

        count = df[column].isna().sum()

        print(
            f"{column}: {count}"
        )

    # --------------------------------------------------------
    # STEP 10: REMOVE INVALID CRITICAL ROWS
    # --------------------------------------------------------

    print()
    print("STEP 10: REMOVING INVALID ROWS")
    print("-" * 70)

    rows_before_invalid = len(df)

    df = df.dropna(
        subset=critical_columns
    )

    rows_after_invalid = len(df)

    invalid_rows_removed = (
        rows_before_invalid
        - rows_after_invalid
    )

    print("Rows before:", rows_before_invalid)
    print("Rows after:", rows_after_invalid)

    print(
        "Invalid rows removed:",
        invalid_rows_removed
    )

    # --------------------------------------------------------
    # STEP 11: CHECK FINANCIAL VALUES
    # --------------------------------------------------------

    print()
    print("STEP 11: CHECKING FINANCIAL VALUES")
    print("-" * 70)

    negative_values = (
        df["value"] < 0
    ).sum()

    zero_values = (
        df["value"] == 0
    ).sum()

    positive_values = (
        df["value"] > 0
    ).sum()

    print(
        "Positive values:",
        positive_values
    )

    print(
        "Zero values:",
        zero_values
    )

    print(
        "Negative values:",
        negative_values
    )

    print()
    print(
        "Negative financial values are NOT automatically removed."
    )

    print(
        "Some legitimate financial metrics can be negative."
    )

    # --------------------------------------------------------
    # STEP 12: CHECK COMPANY CONSISTENCY
    # --------------------------------------------------------

    print()
    print("STEP 12: CHECKING COMPANY CONSISTENCY")
    print("-" * 70)

    companies = (
        df["company_name"]
        .dropna()
        .unique()
        .tolist()
    )

    ciks = (
        df["cik"]
        .dropna()
        .unique()
        .tolist()
    )

    print("Companies found:")

    for company in companies:
        print("-", company)

    print()
    print("CIKs found:")

    for cik in ciks:
        print("-", cik)

    # --------------------------------------------------------
    # STEP 13: CHECK METRICS
    # --------------------------------------------------------

    print()
    print("STEP 13: CHECKING FINANCIAL METRICS")
    print("-" * 70)

    print(
        df["metric"]
        .value_counts()
    )

    # --------------------------------------------------------
    # STEP 14: CHECK SEC FORMS
    # --------------------------------------------------------

    print()
    print("STEP 14: CHECKING SEC FORMS")
    print("-" * 70)

    print(
        df["form"]
        .value_counts(dropna=False)
    )

    # --------------------------------------------------------
    # STEP 15: CHECK UNITS
    # --------------------------------------------------------

    print()
    print("STEP 15: CHECKING FINANCIAL UNITS")
    print("-" * 70)

    print(
        df["unit"]
        .value_counts(dropna=False)
    )

    # --------------------------------------------------------
    # STEP 16: CHECK FISCAL PERIODS
    # --------------------------------------------------------

    print()
    print("STEP 16: CHECKING FISCAL PERIODS")
    print("-" * 70)

    print(
        df["fiscal_period"]
        .value_counts(dropna=False)
    )

    # --------------------------------------------------------
    # STEP 17: CHECK DATE RANGE
    # --------------------------------------------------------

    print()
    print("STEP 17: CHECKING DATE RANGE")
    print("-" * 70)

    earliest_date = df["period_end"].min()
    latest_date = df["period_end"].max()

    print(
        "Earliest period end:",
        earliest_date
    )

    print(
        "Latest period end:",
        latest_date
    )

    # --------------------------------------------------------
    # STEP 18: CHECK FILING DATE RANGE
    # --------------------------------------------------------

    print()
    print("STEP 18: CHECKING FILING DATE RANGE")
    print("-" * 70)

    earliest_filing = df["filing_date"].min()
    latest_filing = df["filing_date"].max()

    print(
        "Earliest filing date:",
        earliest_filing
    )

    print(
        "Latest filing date:",
        latest_filing
    )

    # --------------------------------------------------------
    # STEP 19: SORT DATA
    # --------------------------------------------------------

    print()
    print("STEP 19: SORTING DATA")
    print("-" * 70)

    df = df.sort_values(
        by=[
            "metric",
            "period_end",
            "filing_date",
        ]
    )

    df = df.reset_index(
        drop=True
    )

    print("Data sorted successfully.")

    # --------------------------------------------------------
    # STEP 20: FINAL VALIDATION
    # --------------------------------------------------------

    print()
    print("STEP 20: FINAL VALIDATION")
    print("-" * 70)

    final_missing = df.isna().sum()

    print("Critical missing values:")

    for column in critical_columns:

        print(
            f"{column}:",
            final_missing[column]
        )

    print()
    print(
        "Exact duplicates remaining:",
        df.duplicated().sum()
    )

    print(
        "Final rows:",
        len(df)
    )

    print(
        "Final columns:",
        len(df.columns)
    )

    # --------------------------------------------------------
    # STEP 21: CREATE OUTPUT DIRECTORY
    # --------------------------------------------------------

    print()
    print("STEP 21: PREPARING OUTPUT DIRECTORY")
    print("-" * 70)

    output_directory = os.path.dirname(
        OUTPUT_FILE
    )

    os.makedirs(
        output_directory,
        exist_ok=True
    )

    print(
        "Output directory ready:",
        output_directory
    )

    # --------------------------------------------------------
    # STEP 22: SAVE CLEAN DATA
    # --------------------------------------------------------

    print()
    print("STEP 22: SAVING CLEAN DATA")
    print("-" * 70)

    try:

        df.to_csv(
            OUTPUT_FILE,
            index=False
        )

    except Exception as error:

        print("ERROR while saving cleaned CSV:")
        print(error)
        sys.exit(1)

    print()
    print("Clean file created:")
    print(OUTPUT_FILE)

    # --------------------------------------------------------
    # STEP 23: FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CLEANING COMPLETED SUCCESSFULLY")
    print("=" * 70)

    print()
    print("FINAL DATASET")
    print("-" * 70)

    print("Rows:", len(df))
    print("Columns:", len(df.columns))

    print()
    print("FINAL COLUMNS")
    print("-" * 70)

    for column in df.columns:
        print("-", column)

    print()
    print("METRICS")
    print("-" * 70)

    print(
        df["metric"].value_counts()
    )

    print()
    print("SEC FORMS")
    print("-" * 70)

    print(
        df["form"].value_counts(
            dropna=False
        )
    )

    print()
    print("UNITS")
    print("-" * 70)

    print(
        df["unit"].value_counts(
            dropna=False
        )
    )

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
    print("OUTPUT FILE")
    print("-" * 70)

    print(OUTPUT_FILE)

    print()
    print("=" * 70)
    print("NEXT STEP")
    print("=" * 70)

    print()
    print(
        "Run:"
    )

    print(
        "python data_quality_report.py"
    )

    print()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("Cleaning interrupted by user.")
        sys.exit(1)

    except Exception as error:

        print()
        print("=" * 70)
        print("UNEXPECTED ERROR")
        print("=" * 70)

        print()
        print(error)

        sys.exit(1)
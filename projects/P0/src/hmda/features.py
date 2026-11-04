"""Derived features stored on every cleaned LAR row.

Both run after cleaning, so numeric columns are already floats with nulls
where HMDA reported "NA" or "Exempt".
"""
import numpy as np
import pandas as pd

# Regulators' income levels for community lending exams: tract median family
# income as a % of the metro median. Below 80 is low/moderate, 120+ is upper.
LOW_MODERATE, MIDDLE, UPPER = "Low/Moderate", "Middle", "Upper"
TRACT_INCOME_BANDS = [LOW_MODERATE, MIDDLE, UPPER]

FEATURE_COLUMNS = ["tract_income_band", "loan_to_income"]


def add_tract_income_band(df):
    """Band each row's census tract by its income relative to the metro.

    A percentage of 0 or below is treated as unknown: HMDA reports 0 for
    populated tracts whose census median income isn't available.
    """
    df = df.copy()
    pct = pd.to_numeric(df["tract_to_msa_income_percentage"], errors="coerce")
    known = pct > 0
    band = np.select([pct < 80, pct < 120], [LOW_MODERATE, MIDDLE], default=UPPER)
    df["tract_income_band"] = pd.Series(band, index=df.index).where(known)
    return df


def add_loan_to_income(df):
    """Loan amount over annual income; income is in thousands of dollars.

    Null when income is missing, zero or negative.
    """
    df = df.copy()
    income = pd.to_numeric(df["income"], errors="coerce")
    amount = pd.to_numeric(df["loan_amount"], errors="coerce")
    ratio = (amount / (income * 1000)).round(2)
    df["loan_to_income"] = ratio.where(income > 0).astype("float64")
    return df


def add_features(df):
    return add_loan_to_income(add_tract_income_band(df))

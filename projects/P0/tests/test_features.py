import math

import pandas as pd
import pytest

from hmda.features import FEATURE_COLUMNS, add_features, add_loan_to_income, add_tract_income_band


def band(pct):
    df = add_tract_income_band(pd.DataFrame({"tract_to_msa_income_percentage": [pct]}))
    value = df["tract_income_band"].iloc[0]
    return None if pd.isna(value) else value


def lti(loan_amount, income):
    df = add_loan_to_income(pd.DataFrame({"loan_amount": [loan_amount], "income": [income]}))
    value = df["loan_to_income"].iloc[0]
    return None if pd.isna(value) else value


# ---- tract_income_band: the 80 and 120 cut-offs ----------------------------

@pytest.mark.parametrize("pct, expected", [
    (0.01, "Low/Moderate"),
    (79.99, "Low/Moderate"),
    (80, "Middle"),
    (119.99, "Middle"),
    (120, "Upper"),
    (331, "Upper"),
])
def test_tract_income_band_edges(pct, expected):
    assert band(pct) == expected


@pytest.mark.parametrize("pct", [None, float("nan"), "NA", "", 0, -5])
def test_tract_income_band_unknown(pct):
    assert band(pct) is None


# ---- loan_to_income ----------------------------------------------------------

def test_loan_to_income_uses_income_in_thousands():
    assert lti(255000.0, 104.0) == 2.45


@pytest.mark.parametrize("income", [0, -50, None, float("nan"), "NA"])
def test_loan_to_income_null_without_positive_income(income):
    assert lti(255000.0, income) is None


def test_loan_to_income_null_without_loan_amount():
    assert lti(None, 104.0) is None


# ---- together ----------------------------------------------------------------

def test_add_features_keeps_rows_and_columns():
    df = pd.DataFrame({"lei": ["A", "B"], "tract_to_msa_income_percentage": [85.0, None],
                       "loan_amount": [300000.0, 200000.0], "income": [100.0, 0.0]})
    out = add_features(df)
    assert list(out.columns) == list(df.columns) + FEATURE_COLUMNS
    assert out["tract_income_band"].iloc[0] == "Middle" and pd.isna(out["tract_income_band"].iloc[1])
    assert out["loan_to_income"].iloc[0] == 3.0 and math.isnan(out["loan_to_income"].iloc[1])
    assert out["loan_to_income"].dtype == "float64"
    assert "tract_income_band" not in df            # input left untouched

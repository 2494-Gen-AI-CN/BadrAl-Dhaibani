import json

import pandas as pd
import pytest

from hmda.clean import (DTI_BANDS, apply_scope_filter, clean_filers, clean_lar,
                        fix_not_reported, map_dti, reject_reasons)

COLUMNS = ["activity_year", "lei", "county_code", "census_tract", "action_taken",
           "denial_reason-1", "loan_type", "loan_purpose", "loan_amount", "income",
           "interest_rate", "rate_spread", "debt_to_income_ratio", "applicant_age",
           "property_value"]

GOOD = {
    "activity_year": "2024", "lei": "549300GKFNPRWNS0GF29", "county_code": "39049",
    "census_tract": "39049001000", "action_taken": "1", "denial_reason-1": "10",
    "loan_type": "1", "loan_purpose": "1", "loan_amount": "255000.0", "income": "104",
    "interest_rate": "6.5", "rate_spread": "0.42", "debt_to_income_ratio": "41",
    "applicant_age": "25-34", "property_value": "305000",
    "derived_race": "White",  # raw-only column, dropped from output
}


def frame(*overrides):
    return pd.DataFrame([{**GOOD, **o} for o in overrides])


def reasons(*overrides, seen=None):
    out = reject_reasons(frame(*overrides), set() if seen is None else seen)
    return [r if isinstance(r, str) else None for r in out]


# ---- reject rules: one passing row, one failing row, the reason it writes ----

def test_good_row_passes():
    assert reasons({}) == [None]


@pytest.mark.parametrize("col", ["lei", "county_code", "census_tract", "action_taken"])
@pytest.mark.parametrize("value", ["", "NA"])
def test_missing_key(col, value):
    assert reasons({col: value}) == ["missing_key"]


@pytest.mark.parametrize("lei", ["549300gkfnprwns0gf29", "549300GKFNPRWNS0GF2", "549300GKFNPRWNS0GF29X",
                                 "549300GKFNPRWNS0-F29"])
def test_bad_lei(lei):
    assert reasons({"lei": lei}) == ["bad_lei"]


def test_tract_county_mismatch():
    assert reasons({"census_tract": "37049001000"}) == ["tract_county_mismatch"]


@pytest.mark.parametrize("amount", ["0", "-5000", "abc", "Exempt"])
def test_bad_loan_amount(amount):
    assert reasons({"loan_amount": amount}) == ["bad_loan_amount"]


def test_first_failing_rule_wins():
    assert reasons({"lei": "short", "loan_amount": "0"}) == ["bad_lei"]


def test_exact_duplicate_rejected_once():
    assert reasons({}, {}) == [None, "duplicate"]


def test_rows_differing_only_in_dropped_column_are_not_duplicates():
    assert reasons({}, {"derived_race": "Asian"}) == [None, None]


def test_duplicates_tracked_across_chunks():
    seen = set()
    assert reasons({}, seen=seen) == [None]
    assert reasons({}, seen=seen) == ["duplicate"]


# ---- fix rules ---------------------------------------------------------------

@pytest.mark.parametrize("marker", ["Exempt", "NA", ""])
def test_markers_in_numeric_fields_become_null(marker):
    good, _ = clean_lar(frame({"property_value": marker, "interest_rate": marker}), COLUMNS, set())
    assert pd.isna(good.loc[0, "property_value"])
    assert pd.isna(good.loc[0, "interest_rate"])


@pytest.mark.parametrize("marker", ["1111", "8888", "9999", "Exempt"])
def test_markers_in_coded_fields_become_null(marker):
    out = fix_not_reported(frame({"denial_reason-1": marker, "applicant_age": marker}))
    assert pd.isna(out.loc[0, "denial_reason-1"])
    assert pd.isna(out.loc[0, "applicant_age"])


def test_8888_kept_in_continuous_field():
    out = fix_not_reported(frame({"income": "8888"}))
    assert out.loc[0, "income"] == "8888"


def test_types_after_cleaning():
    good, _ = clean_lar(frame({}), COLUMNS, set())
    assert good.loc[0, "loan_amount"] == 255000.0
    assert good.loc[0, "action_taken"] == 1
    assert good.loc[0, "county_code"] == "39049"  # keys stay strings
    assert "denial_reason_1" in good.columns and "derived_race" not in good.columns


@pytest.mark.parametrize("income", ["-50", "NA"])
def test_bad_income_nulled_row_kept(income):
    good, rejects = clean_lar(frame({"income": income}), COLUMNS, set())
    assert len(good) == 1 and rejects.empty
    assert pd.isna(good.loc[0, "income"])


def test_zero_income_kept():
    good, _ = clean_lar(frame({"income": "0"}), COLUMNS, set())
    assert good.loc[0, "income"] == 0


# Every value seen in the 2023 and 2025 files
RAW_DTI = ["<20%", "20%-<30%", "30%-<36%", "50%-60%", ">60%",
           *[str(v) for v in range(36, 50)]]


@pytest.mark.parametrize("raw", RAW_DTI)
def test_every_dti_value_lands_in_one_band(raw):
    band = map_dti(frame({"debt_to_income_ratio": raw})).loc[0, "debt_to_income_ratio"]
    assert band in set(DTI_BANDS.values())


@pytest.mark.parametrize("raw, band", [("36", "36%-<43%"), ("42", "36%-<43%"),
                                       ("43", "43%-<50%"), ("49", "43%-<50%")])
def test_dti_band_edges(raw, band):
    assert map_dti(frame({"debt_to_income_ratio": raw})).loc[0, "debt_to_income_ratio"] == band


@pytest.mark.parametrize("raw", ["NA", "Exempt"])
def test_dti_not_reported_is_null(raw):
    assert pd.isna(map_dti(frame({"debt_to_income_ratio": raw})).loc[0, "debt_to_income_ratio"])


def test_unknown_dti_value_fails_loudly():
    with pytest.raises(ValueError, match="55"):
        map_dti(frame({"debt_to_income_ratio": "55"}))


@pytest.mark.parametrize("action", ["2", "3", "4", "5"])
def test_rates_nulled_unless_originated(action):
    good, _ = clean_lar(frame({"action_taken": action}), COLUMNS, set())
    assert pd.isna(good.loc[0, "interest_rate"]) and pd.isna(good.loc[0, "rate_spread"])


def test_rates_kept_when_originated():
    good, _ = clean_lar(frame({}), COLUMNS, set())
    assert good.loc[0, "rate_spread"] == 0.42


# ---- scope filter and outputs ------------------------------------------------

def test_refinance_is_filtered_not_rejected():
    df = frame({}, {"loan_purpose": "31"})
    in_scope, n_filtered = apply_scope_filter(df, {"loan_purpose": [1]})
    assert n_filtered == 1
    good, rejects = clean_lar(in_scope, COLUMNS, set())
    assert len(good) == 1 and rejects.empty


def test_rejects_carry_reason_and_raw_record():
    good, rejects = clean_lar(frame({}, {"lei": "NA"}), COLUMNS, set())
    assert len(good) == 1
    assert list(rejects["reject_reason"]) == ["missing_key"]
    assert json.loads(rejects.loc[0, "raw_record"])["lei"] == "NA"


def test_duplicate_filer_rejected():
    raw = pd.DataFrame([
        {"lei": "549300GKFNPRWNS0GF29", "name": "CMG MORTGAGE, INC.", "count": 848, "period": 2024},
        {"lei": "549300GKFNPRWNS0GF29", "name": "CMG Mortgage", "count": 848, "period": 2024},
        {"lei": "549300GKFNPRWNS0GF29", "name": "CMG MORTGAGE, INC.", "count": 900, "period": 2025},
    ])
    good, rejects = clean_filers(raw)
    assert len(good) == 2
    assert list(rejects["reject_reason"]) == ["duplicate_filer"]

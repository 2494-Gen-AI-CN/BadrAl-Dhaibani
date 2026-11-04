"""Cleansing rules for HMDA loan (LAR) and filer rows.

Raw frames arrive with every value as a string (read with dtype=str and
keep_default_na=False), so "NA" and "Exempt" are still literal text.

Reject rules send a row to rejects with the rule name as its reason; the first
failing rule wins. Fix rules keep the row and clean the value.
"""
import json

import numpy as np
import pandas as pd

KEY_COLUMNS = ["lei", "county_code", "census_tract", "action_taken"]
MISSING = {"", "NA", "Exempt"}

# Coded fields: 1111 = exempt, 8888/9999 = not reported / not applicable
CODE_COLUMNS = ["activity_year", "action_taken", "loan_type", "loan_purpose", "lien_status",
                "occupancy_type", "business_or_commercial_purpose",
                "denial_reason-1", "denial_reason-2", "denial_reason-3", "denial_reason-4"]
CODE_MARKERS = MISSING | {"1111", "8888", "9999"}

# Continuous fields only use "NA" / "Exempt"; 8888 could be a real value here
NUMERIC_COLUMNS = ["loan_amount", "property_value", "income", "interest_rate", "rate_spread",
                   "loan_term", "loan_to_value_ratio", "tract_to_msa_income_percentage",
                   "tract_population"]

RATE_COLUMNS = ["interest_rate", "rate_spread"]
ORIGINATED = 1

# Underwriting bands; keeps the 43% qualified-mortgage line visible
DTI_BANDS = {
    "<20%": "<20%",
    "20%-<30%": "20%-<30%",
    "30%-<36%": "30%-<36%",
    **{str(v): "36%-<43%" for v in range(36, 43)},
    **{str(v): "43%-<50%" for v in range(43, 50)},
    "50%-60%": "50%-60%",
    ">60%": ">60%",
}


# ---- scope filter --------------------------------------------------------

def apply_scope_filter(df, filters):
    """Keep rows inside the config filters. Returns (in_scope, n_filtered)."""
    keep = pd.Series(True, index=df.index)
    for col, allowed in filters.items():
        keep &= df[col].isin([str(v) for v in allowed])
    return df[keep], int((~keep).sum())


# ---- reject rules: each returns a boolean mask of failing rows ------------

def missing_key(df):
    return df[KEY_COLUMNS].isin(MISSING).any(axis=1)


def bad_lei(df):
    return ~df["lei"].str.fullmatch(r"[A-Z0-9]{20}")


def tract_county_mismatch(df):
    starts = [t.startswith(c) for t, c in zip(df["census_tract"], df["county_code"])]
    return ~pd.Series(starts, index=df.index, dtype=bool)


def bad_loan_amount(df):
    amount = pd.to_numeric(df["loan_amount"], errors="coerce")
    return ~(amount > 0)


ROW_RULES = [missing_key, bad_lei, tract_county_mismatch, bad_loan_amount]

# Every reason a row can be rejected with; the load log has one count column per reason
REJECT_REASONS = [r.__name__ for r in ROW_RULES] + ["duplicate", "duplicate_filer"]


def duplicate(df, seen):
    """Rows identical in every raw column to one already seen in this file.

    Uses all raw columns: rows that match on the kept columns can still differ
    in columns we drop (race, sex), and those are separate applications.
    `seen` carries row hashes across chunks of the same file.
    """
    hashes = pd.util.hash_pandas_object(df, index=False)
    dup = hashes.duplicated() | hashes.isin(seen)
    seen.update(hashes[~dup])
    return dup


def reject_reasons(df, seen):
    """Reason for each row (first failing rule), or None for good rows."""
    reason = pd.Series(None, index=df.index, dtype=object)
    for rule in ROW_RULES:
        reason = reason.mask(reason.isna() & rule(df), rule.__name__)
    still_good = reason.isna()
    dup = duplicate(df[still_good], seen)
    reason.loc[dup[dup].index] = "duplicate"
    return reason


# ---- fix rules -----------------------------------------------------------

def fix_not_reported(df):
    """Set not-reported markers to null in coded, numeric and bucket fields."""
    df = df.copy()
    for col in CODE_COLUMNS:
        if col in df:
            df[col] = df[col].mask(df[col].isin(CODE_MARKERS))
    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = df[col].mask(df[col].isin(MISSING))
    if "applicant_age" in df:
        df["applicant_age"] = df["applicant_age"].mask(df["applicant_age"].isin(CODE_MARKERS))
    return df


def cast_types(df):
    df = df.copy()
    for col in CODE_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def fix_income(df):
    """Negative income becomes null; the row stays but drops out of income ratios."""
    df = df.copy()
    df["income"] = df["income"].mask(df["income"] < 0)
    return df


def map_dti(df):
    """Map HMDA's mix of ranges and single values 36-49 onto one band scheme."""
    df = df.copy()
    raw = df["debt_to_income_ratio"]
    reported = ~raw.isin(MISSING)
    unknown = sorted(set(raw[reported]) - DTI_BANDS.keys())
    if unknown:
        raise ValueError(f"unmapped debt_to_income_ratio values: {unknown}")
    df["debt_to_income_ratio"] = raw.map(DTI_BANDS).where(reported)
    return df


def fix_rate_fields(df):
    """Rates only mean something for originated loans."""
    df = df.copy()
    not_originated = df["action_taken"] != ORIGINATED
    for col in RATE_COLUMNS:
        df[col] = df[col].mask(not_originated)
    return df


FIXES = [fix_not_reported, cast_types, fix_income, map_dti, fix_rate_fields]


# ---- entry points ----------------------------------------------------------

def _to_rejects(df, reason):
    records = df.to_dict(orient="records")
    return pd.DataFrame({
        "reject_reason": reason.to_numpy(),
        "raw_record": [json.dumps(r) for r in records],
    })


def clean_lar(raw, columns, seen):
    """Clean one in-scope chunk of raw LAR rows (all raw columns, as strings).

    Returns (good, rejects). good holds only `columns`, typed and fixed, with
    hyphens in names turned to underscores for BigQuery.
    """
    reason = reject_reasons(raw, seen)
    bad = reason.notna()
    rejects = _to_rejects(raw.loc[bad, columns], reason[bad])

    good = raw.loc[~bad, columns]
    for fix in FIXES:
        good = fix(good)
    good.columns = [c.replace("-", "_") for c in good.columns]
    return good.reset_index(drop=True), rejects


def clean_filers(raw):
    """Clean one year's filers: one name per LEI per period."""
    dup = raw.duplicated(subset=["lei", "period"], keep="first")
    reason = pd.Series(np.where(dup, "duplicate_filer", None), index=raw.index)
    rejects = _to_rejects(raw[dup], reason[dup])
    good = raw[~dup].copy()
    good["name"] = good["name"].str.strip()
    good["period"] = good["period"].astype("int64")
    return good.reset_index(drop=True), rejects

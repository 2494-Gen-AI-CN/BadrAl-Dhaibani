"""Size check: compare API row counts with the downloaded files and
show how many rows survive the ingest filter.

Usage: python3 scripts/row_counts.py   (stdlib only, run after download.sh)
"""
import csv
import json
import urllib.request
from pathlib import Path

STATES = ["OH", "NC"]
YEARS = [2023, 2024, 2025]
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
AGG_URL = ("https://ffiec.cfpb.gov/v2/data-browser-api/view/aggregations"
           "?states={state}&years={year}&actions_taken=1,2,3,4,5,6,7,8")

# Mirrors the planned config.yaml filters
FILTERS = {
    "loan_purpose": {"1"},
    "lien_status": {"1"},
    "occupancy_type": {"1"},
    "business_or_commercial_purpose": {"2"},
    "action_taken": {"1", "2", "3", "4", "5"},
}


def api_count(state, year):
    with urllib.request.urlopen(AGG_URL.format(state=state, year=year)) as r:
        return sum(a["count"] for a in json.load(r)["aggregations"])


def file_counts(path):
    total = kept = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            if (all(row[col] in ok for col, ok in FILTERS.items())
                    and row["derived_dwelling_category"].startswith("Single Family")):
                kept += 1
    return total, kept


def main():
    print(f"{'file':<18}{'api_rows':>10}{'file_rows':>11}{'match':>7}{'filtered':>10}{'filers':>8}")
    grand = 0
    for state in STATES:
        for year in YEARS:
            api = api_count(state, year)
            total, kept = file_counts(RAW / f"lar_{state}_{year}.csv")
            filers = json.loads((RAW / f"filers_{state}_{year}.json").read_text())
            grand += kept
            print(f"lar_{state}_{year:<10}{api:>10,}{total:>11,}{'yes' if api == total else 'NO':>7}"
                  f"{kept:>10,}{len(filers['institutions']):>8,}")
    print(f"\nfiltered rows, all files: {grand:,}")


if __name__ == "__main__":
    main()

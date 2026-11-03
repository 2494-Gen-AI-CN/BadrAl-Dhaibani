"""End-to-end runs against an in-memory warehouse; nothing touches BigQuery."""
import json
from pathlib import Path

import pandas as pd
import pytest

from hmda.config import parse_config
from hmda.run import run

LAR_COLUMNS = ["activity_year", "lei", "county_code", "census_tract", "action_taken",
               "loan_purpose", "loan_amount", "income", "debt_to_income_ratio",
               "interest_rate", "rate_spread"]

ROW = {"activity_year": "2024", "lei": "549300GKFNPRWNS0GF29", "county_code": "39049",
       "census_tract": "39049001000", "action_taken": "1", "loan_purpose": "1",
       "loan_amount": "255000", "income": "104", "debt_to_income_ratio": "41",
       "interest_rate": "6.5", "rate_spread": "0.42", "derived_race": "White"}


class FakeWarehouse:
    """Same interface as BigQueryWarehouse: per-source tables plus views."""

    def __init__(self):
        self.tables, self.views, self.log = {}, {}, []

    def ensure_dataset(self):
        pass

    def load_log(self):
        return [dict(r) for r in self.log]

    def list_tables(self):
        return set(self.tables)

    def replace_table(self, table, df, schema=None):
        if df.empty:
            self.tables.pop(table, None)
        else:
            self.tables[table] = df.copy()

    def replace_view(self, view, tables):
        if tables:
            self.views[view] = list(tables)
        else:
            self.views.pop(view, None)

    def append_log(self, row):
        self.log.append(row)

    def rows(self, view, source=None):
        """Read through a view, as downstream SQL would."""
        frames = [self.tables[t] for t in self.views.get(view, [])]
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["source_name"])
        return df if source is None else df[df["source_name"] == source]


def write_lar(path, *overrides):
    pd.DataFrame([{**ROW, **o} for o in overrides]).to_csv(path, index=False)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    write_lar(tmp_path / "lar.csv",
              {}, {"income": "90"}, {"income": "90"},          # exact duplicate
              {"lei": "NA"},                                     # missing_key
              {"loan_purpose": "31"})                            # filtered (refinance)
    (tmp_path / "filers.json").write_text(json.dumps({"institutions": [
        {"lei": "549300GKFNPRWNS0GF29", "name": " CMG MORTGAGE ", "count": 3, "period": 2024},
        {"lei": "549300GKFNPRWNS0GF29", "name": "CMG Mortgage", "count": 3, "period": 2024}]}))
    (tmp_path / "counties.txt").write_text(
        "STATE|STATEFP|COUNTYFP|COUNTYNAME\nOH|39|049|Franklin County\n"
        "NC|37|119|Mecklenburg County\nAL|01|001|Autauga County\n")
    cfg = parse_config({
        "bigquery": {"project": "${GCP_PROJECT}", "dataset": "hmda_staging", "location": "US"},
        "sources": [
            {"name": "lar_oh_2024", "path": "lar.csv", "format": "csv", "kind": "lar"},
            {"name": "filers_oh_2024", "path": "filers.json", "format": "json", "kind": "filers"},
            {"name": "counties_2020", "path": "counties.txt", "format": "csv", "kind": "counties",
             "delimiter": "|", "states": ["OH", "NC"]},
        ],
        "filters": {"loan_purpose": [1]},
        "lar_columns": LAR_COLUMNS,
        "chunk_size": 2,                       # several chunks, so duplicates cross chunks
    }, base=tmp_path)
    return cfg, FakeWarehouse(), tmp_path


def by_source(rows):
    return {r["source_name"]: r for r in rows}


def test_first_run_loads_everything_with_counts(setup):
    cfg, wh, _ = setup
    log = by_source(run(cfg, wh, run_id="r1", echo=lambda _: None))
    lar = log["lar_oh_2024"]
    assert lar["status"] == "loaded"
    assert (lar["rows_read"], lar["rows_filtered"], lar["rows_rejected"], lar["rows_loaded"]) == (5, 1, 2, 2)
    assert lar["rows_missing_key"] == 1 and lar["rows_duplicate"] == 1 and lar["rows_bad_lei"] == 0
    assert log["filers_oh_2024"]["rows_duplicate_filer"] == 1
    assert log["counties_2020"]["rows_filtered"] == 1 and log["counties_2020"]["rows_loaded"] == 2

    assert len(wh.rows("stg_lar")) == 2
    assert set(wh.rows("stg_lar")["source_name"]) == {"lar_oh_2024"}
    assert list(wh.rows("stg_filers")["name"]) == ["CMG MORTGAGE"]
    assert sorted(wh.rows("stg_counties")["county_code"]) == ["37119", "39049"]
    rejects = wh.rows("rejects")
    assert sorted(rejects["reject_reason"]) == ["duplicate", "duplicate_filer", "missing_key"]
    assert set(rejects["run_id"]) == {"r1"}


def test_second_run_skips_and_adds_nothing(setup):
    cfg, wh, _ = setup
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    before = {t: len(df) for t, df in wh.tables.items()}
    second = run(cfg, wh, run_id="r2", echo=lambda _: None)
    assert {r["status"] for r in second} == {"skipped"}
    assert all(r["rows_read"] is None for r in second)
    assert {t: len(df) for t, df in wh.tables.items()} == before
    assert len(wh.log) == 6                     # one row per source per run


def test_changed_file_replaces_its_rows_only(setup):
    cfg, wh, tmp = setup
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    write_lar(tmp / "lar.csv", {}, {"income": "50"}, {"income": "60"})
    log = by_source(run(cfg, wh, run_id="r2", echo=lambda _: None))
    assert log["lar_oh_2024"]["status"] == "loaded"
    assert log["filers_oh_2024"]["status"] == "skipped"
    assert sorted(wh.rows("stg_lar")["income"]) == [50, 60, 104]
    assert len(wh.rows("rejects", "lar_oh_2024")) == 0     # old rejects went with the old file
    assert len(wh.rows("rejects", "filers_oh_2024")) == 1


def test_force_reloads_unchanged_files(setup):
    cfg, wh, _ = setup
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    second = run(cfg, wh, force=True, run_id="r2", echo=lambda _: None)
    assert {r["status"] for r in second} == {"loaded"}
    assert len(wh.rows("stg_lar")) == 2


def test_failed_source_is_logged_and_others_still_load(setup):
    cfg, wh, tmp = setup
    write_lar(tmp / "lar.csv", {"debt_to_income_ratio": "55"})   # unmapped DTI raises
    log = by_source(run(cfg, wh, run_id="r1", echo=lambda _: None))
    assert log["lar_oh_2024"]["status"] == "failed"
    assert "55" in log["lar_oh_2024"]["error"]
    assert log["filers_oh_2024"]["status"] == "loaded"

    write_lar(tmp / "lar.csv", {})                                # fixed: next run retries it
    log = by_source(run(cfg, wh, run_id="r2", echo=lambda _: None))
    assert log["lar_oh_2024"]["status"] == "loaded"


def test_missing_file_fails_without_hash(setup):
    cfg, wh, tmp = setup
    (tmp / "filers.json").unlink()
    log = by_source(run(cfg, wh, run_id="r1", echo=lambda _: None))
    assert log["filers_oh_2024"]["status"] == "failed"
    assert log["filers_oh_2024"]["file_sha256"] is None
    assert "FileNotFoundError" in log["filers_oh_2024"]["error"]


def test_one_table_per_source_and_views_stack_them(setup):
    cfg, wh, _ = setup
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    assert set(wh.tables) == {
        "stg_lar__lar_oh_2024", "stg_filers__filers_oh_2024", "stg_counties__counties_2020",
        "rejects__lar_oh_2024", "rejects__filers_oh_2024"}   # counties have no rejects
    assert wh.views["stg_lar"] == ["stg_lar__lar_oh_2024"]
    assert wh.views["rejects"] == ["rejects__lar_oh_2024", "rejects__filers_oh_2024"]


def test_rejects_table_dropped_when_new_file_has_none(setup):
    cfg, wh, tmp = setup
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    write_lar(tmp / "lar.csv", {})
    run(cfg, wh, run_id="r2", echo=lambda _: None)
    assert "rejects__lar_oh_2024" not in wh.tables
    assert wh.views["rejects"] == ["rejects__filers_oh_2024"]


def test_failed_source_left_out_of_views(setup):
    cfg, wh, tmp = setup
    (tmp / "lar.csv").unlink()
    run(cfg, wh, run_id="r1", echo=lambda _: None)
    assert "stg_lar" not in wh.views
    assert wh.views["stg_filers"] == ["stg_filers__filers_oh_2024"]

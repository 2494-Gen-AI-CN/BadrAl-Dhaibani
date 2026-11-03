from datetime import datetime, timezone

import pandas as pd

from hmda.load import (COUNT_COLUMNS, FAILED, LOADED, SKIPPED, file_sha256, is_unchanged,
                       log_row, new_run_id, schema_for)


def entry(run_id, sha, status=LOADED, source="lar_oh_2024"):
    return {"run_id": run_id, "source_name": source, "file_sha256": sha, "status": status}


# ---- skip check, against an in-memory load log -------------------------------

def test_known_hash_is_skipped():
    assert is_unchanged([entry("2026-11-04T14:00:00Z", "aaa")], "lar_oh_2024", "aaa")


def test_changed_hash_is_loaded():
    assert not is_unchanged([entry("2026-11-04T14:00:00Z", "aaa")], "lar_oh_2024", "bbb")


def test_new_source_is_loaded():
    assert not is_unchanged([], "lar_oh_2024", "aaa")


def test_same_hash_for_other_source_does_not_count():
    log = [entry("2026-11-04T14:00:00Z", "aaa", source="lar_nc_2024")]
    assert not is_unchanged(log, "lar_oh_2024", "aaa")


def test_failed_load_does_not_count():
    assert not is_unchanged([entry("2026-11-04T14:00:00Z", "aaa", FAILED)], "lar_oh_2024", "aaa")


def test_skipped_rows_keep_the_file_skipped():
    log = [entry("2026-11-04T14:00:00Z", "aaa"), entry("2026-11-05T09:00:00Z", "aaa", SKIPPED)]
    assert is_unchanged(log, "lar_oh_2024", "aaa")


def test_file_put_back_after_a_change_is_reloaded():
    log = [entry("2026-11-04T14:00:00Z", "aaa"), entry("2026-11-05T09:00:00Z", "bbb")]
    assert not is_unchanged(log, "lar_oh_2024", "aaa")
    assert is_unchanged(log, "lar_oh_2024", "bbb")


# ---- helpers -----------------------------------------------------------------

def test_run_id_format():
    now = datetime(2026, 11, 4, 14, 2, 11, tzinfo=timezone.utc)
    assert new_run_id(now) == "2026-11-04T14:02:11Z"


def test_file_sha256_changes_with_content(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    first = file_sha256(f)
    assert len(first) == 64 and first == file_sha256(f)
    f.write_text("x\n2\n")
    assert file_sha256(f) != first


def test_log_row_has_every_count_column():
    row = log_row("r", "lar_oh_2024", "aaa", LOADED, {"rows_read": 10, "rows_duplicate": 2})
    assert row["rows_read"] == 10 and row["rows_duplicate"] == 2
    assert row["rows_missing_key"] is None
    assert {"rows_missing_key", "rows_duplicate", "rows_duplicate_filer"} <= set(COUNT_COLUMNS)


def test_schema_for_maps_dtypes():
    df = pd.DataFrame({"a": pd.array([1, None], dtype="Int64"), "b": [1.5, None],
                       "c": ["x", None]})
    assert [(f.name, f.field_type) for f in schema_for(df)] == [
        ("a", "INT64"), ("b", "FLOAT64"), ("c", "STRING")]


def test_source_table_name():
    from hmda.load import source_table
    assert source_table("stg_lar", "lar_oh_2024") == "stg_lar__lar_oh_2024"

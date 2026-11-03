import copy
from pathlib import Path

import pytest

from hmda.config import ConfigError, load_config, parse_config

P0 = Path(__file__).resolve().parent.parent

BASE = {
    "bigquery": {"project": "${GCP_PROJECT}", "dataset": "hmda_staging", "location": "US"},
    "sources": [
        {"name": "lar_oh_2024", "path": "data/raw/lar_OH_2024.csv", "format": "csv", "kind": "lar"},
        {"name": "filers_oh_2024", "path": "data/raw/filers_OH_2024.json", "format": "json", "kind": "filers"},
    ],
    "filters": {"loan_purpose": [1]},
    "lar_columns": ["lei", "loan_purpose"],
    "chunk_size": 1000,
}


@pytest.fixture
def raw(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    return copy.deepcopy(BASE)


def test_valid_config_parses(raw):
    cfg = parse_config(raw, base=Path("/p0"))
    assert cfg.bigquery["project"] == "test-project"
    assert cfg.sources[0].path == Path("/p0/data/raw/lar_OH_2024.csv")
    assert cfg.sources[0].delimiter == ","
    assert [s.name for s in cfg.sources_of("filers")] == ["filers_oh_2024"]


def test_missing_format_fails_clearly(raw):
    del raw["sources"][0]["format"]
    with pytest.raises(ConfigError, match="source lar_oh_2024: missing 'format'"):
        parse_config(raw)


def test_unknown_kind_fails_clearly(raw):
    raw["sources"][1]["kind"] = "lenders"
    with pytest.raises(ConfigError, match="source filers_oh_2024: unknown kind 'lenders'"):
        parse_config(raw)


def test_unknown_format_fails_clearly(raw):
    raw["sources"][0]["format"] = "parquet"
    with pytest.raises(ConfigError, match="unknown format 'parquet'"):
        parse_config(raw)


def test_duplicate_source_names_fail(raw):
    raw["sources"][1]["name"] = "lar_oh_2024"
    with pytest.raises(ConfigError, match="duplicate names"):
        parse_config(raw)


def test_unset_env_var_fails(raw, monkeypatch):
    monkeypatch.delenv("GCP_PROJECT")
    with pytest.raises(ConfigError, match="GCP_PROJECT is not set"):
        parse_config(raw)


def test_filter_column_must_be_read(raw):
    raw["filters"]["lien_status"] = [1]
    with pytest.raises(ConfigError, match="lien_status"):
        parse_config(raw)


def test_bad_chunk_size_fails(raw):
    raw["chunk_size"] = 0
    with pytest.raises(ConfigError, match="chunk_size"):
        parse_config(raw)


COUNTIES = {"name": "counties_2020", "path": "data/raw/counties_2020.txt", "format": "csv",
            "kind": "counties", "delimiter": "|"}


def test_counties_need_states(raw):
    raw["sources"].append(dict(COUNTIES))
    with pytest.raises(ConfigError, match="counties_2020: 'states' must be a non-empty list"):
        parse_config(raw)


def test_states_only_on_counties(raw):
    raw["sources"][0]["states"] = ["OH"]
    with pytest.raises(ConfigError, match="'states' only applies to counties"):
        parse_config(raw)


def test_counties_states_parse(raw):
    raw["sources"].append({**COUNTIES, "states": ["OH", "NC"]})
    assert parse_config(raw).sources_of("counties")[0].states == ("OH", "NC")


def test_project_config_loads(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    cfg = load_config(P0 / "config.yaml")
    assert len(cfg.sources_of("lar")) == 6
    assert len(cfg.sources_of("filers")) == 6
    assert cfg.sources_of("counties")[0].delimiter == "|"

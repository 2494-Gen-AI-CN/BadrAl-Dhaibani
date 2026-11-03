"""Load and validate config.yaml.

Values written as ${VAR} are filled from the environment, after loading .env
from the config's folder. Any problem raises ConfigError with a message that
names the offending source or key.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

FORMATS = {"csv", "json"}
KINDS = {"lar", "filers", "counties"}
BIGQUERY_KEYS = ("project", "dataset", "location")
_ENV_VAR = re.compile(r"\$\{(\w+)\}")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    path: Path
    format: str
    kind: str
    delimiter: str = ","
    states: tuple = ()          # counties only: state abbreviations to keep


@dataclass(frozen=True)
class Config:
    bigquery: dict
    sources: list
    filters: dict
    lar_columns: list
    chunk_size: int

    def sources_of(self, kind):
        return [s for s in self.sources if s.kind == kind]


def _expand_env(value):
    def sub(match):
        var = match.group(1)
        if not os.environ.get(var):
            raise ConfigError(f"environment variable {var} is not set (add it to .env)")
        return os.environ[var]
    return _ENV_VAR.sub(sub, value) if isinstance(value, str) else value


def _parse_source(i, raw, base):
    if not isinstance(raw, dict):
        raise ConfigError(f"sources[{i}] must be a mapping")
    label = raw.get("name", f"sources[{i}]")
    for key in ("name", "path", "format", "kind"):
        if not raw.get(key):
            raise ConfigError(f"source {label}: missing '{key}'")
    if raw["format"] not in FORMATS:
        raise ConfigError(f"source {label}: unknown format '{raw['format']}' "
                          f"(expected one of {sorted(FORMATS)})")
    if raw["kind"] not in KINDS:
        raise ConfigError(f"source {label}: unknown kind '{raw['kind']}' "
                          f"(expected one of {sorted(KINDS)})")
    states = raw.get("states")
    if raw["kind"] == "counties":
        if not isinstance(states, list) or not states or not all(isinstance(s, str) for s in states):
            raise ConfigError(f"source {label}: 'states' must be a non-empty list of state "
                              f"abbreviations, e.g. [OH, NC]")
    elif states is not None:
        raise ConfigError(f"source {label}: 'states' only applies to counties sources")
    return Source(name=raw["name"], path=base / raw["path"], format=raw["format"],
                  kind=raw["kind"], delimiter=raw.get("delimiter", ","),
                  states=tuple(states or ()))


def parse_config(raw, base=Path(".")):
    """Validate an already-loaded config dict; base resolves relative paths."""
    if not isinstance(raw, dict):
        raise ConfigError("config must be a YAML mapping")

    bq = raw.get("bigquery") or {}
    for key in BIGQUERY_KEYS:
        if not bq.get(key):
            raise ConfigError(f"bigquery: missing '{key}'")
    bq = {k: _expand_env(v) for k, v in bq.items()}

    raw_sources = raw.get("sources") or []
    if not raw_sources:
        raise ConfigError("sources: at least one source is required")
    sources = [_parse_source(i, s, base) for i, s in enumerate(raw_sources)]
    names = [s.name for s in sources]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ConfigError(f"sources: duplicate names {dupes}")

    filters = raw.get("filters") or {}
    for col, allowed in filters.items():
        if not isinstance(allowed, list) or not allowed:
            raise ConfigError(f"filters.{col}: must be a non-empty list")

    lar_columns = raw.get("lar_columns") or []
    if any(s.kind == "lar" for s in sources) and not lar_columns:
        raise ConfigError("lar_columns: required when there are lar sources")
    missing = [c for c in filters if c not in lar_columns]
    if missing:
        raise ConfigError(f"filters use columns not in lar_columns: {missing}")

    chunk_size = raw.get("chunk_size", 100_000)
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ConfigError("chunk_size: must be a positive integer")

    return Config(bigquery=bq, sources=sources, filters=filters,
                  lar_columns=lar_columns, chunk_size=chunk_size)


def load_config(path="config.yaml"):
    path = Path(path).resolve()
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    load_dotenv(path.parent / ".env")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return parse_config(raw, base=path.parent)

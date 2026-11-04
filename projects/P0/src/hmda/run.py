"""Ingestion entry point: read every source in config.yaml, clean it and load
it into the staging dataset, appending one load_log row per source.

    python -m hmda.run                 # load new or changed files, skip the rest
    python -m hmda.run --force         # reload every file
    python -m hmda.run --config other.yaml

Exits non-zero if any source failed; the other sources still load.
"""
import argparse
import json
import sys
from dataclasses import dataclass

import pandas as pd

from hmda.clean import REJECT_REASONS, apply_scope_filter, clean_filers, clean_lar
from hmda.config import load_config
from hmda.features import add_features
from hmda.load import (COUNT_COLUMNS, FAILED, LOADED, REJECTS_SCHEMA, REJECTS_TABLE,
                       SKIPPED, STAGING_TABLES, BigQueryWarehouse, file_sha256,
                       is_unchanged, log_row, new_run_id, source_table)


@dataclass
class Result:
    good: pd.DataFrame
    rejects: pd.DataFrame
    counts: dict


def _counts(rows_read, rows_filtered, rejects, rows_loaded):
    by_reason = rejects["reject_reason"].value_counts()
    counts = {"rows_read": rows_read, "rows_filtered": rows_filtered,
              "rows_rejected": len(rejects), "rows_loaded": rows_loaded,
              **{f"rows_{r}": int(by_reason.get(r, 0)) for r in REJECT_REASONS}}
    if rows_read != rows_filtered + len(rejects) + rows_loaded:
        raise RuntimeError(f"row counts don't add up: {counts}")
    return counts


def _concat(frames):
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_lar(source, cfg):
    """Chunked read; every raw column is kept until cleaning so the duplicate
    rule can compare whole rows. Features are added to the cleaned rows."""
    seen, goods, rejects = set(), [], []
    rows_read = rows_filtered = 0
    chunks = pd.read_csv(source.path, sep=source.delimiter, dtype=str,
                         keep_default_na=False, chunksize=cfg.chunk_size)
    for chunk in chunks:
        rows_read += len(chunk)
        in_scope, n_filtered = apply_scope_filter(chunk, cfg.filters)
        rows_filtered += n_filtered
        good, rej = clean_lar(in_scope, cfg.lar_columns, seen)
        goods.append(add_features(good))
        rejects.append(rej)
    good, rej = _concat(goods), _concat(rejects)
    return Result(good, rej, _counts(rows_read, rows_filtered, rej, len(good)))


def read_filers(source, cfg):
    with open(source.path) as f:
        raw = pd.DataFrame(json.load(f)["institutions"])
    good, rej = clean_filers(raw)
    return Result(good, rej, _counts(len(raw), 0, rej, len(good)))


def read_counties(source, cfg):
    """Census county reference: keep the configured states, add the 5-digit
    county_code the LAR uses."""
    raw = pd.read_csv(source.path, sep=source.delimiter, dtype=str, keep_default_na=False)
    raw.columns = [c.lower() for c in raw.columns]
    keep = raw["state"].isin(source.states)
    good = raw[keep].copy()
    good["county_code"] = good["statefp"] + good["countyfp"]
    no_rejects = pd.DataFrame(columns=["reject_reason", "raw_record"])
    return Result(good.reset_index(drop=True), no_rejects,
                  _counts(len(raw), int((~keep).sum()), no_rejects, len(good)))


READERS = {"lar": read_lar, "filers": read_filers, "counties": read_counties}


def load_source(source, cfg, warehouse, run_id, sha):
    result = READERS[source.kind](source, cfg)
    good = result.good.assign(source_name=source.name)
    rejects = result.rejects.assign(run_id=run_id, source_name=source.name)
    rejects = rejects[[f.name for f in REJECTS_SCHEMA]]
    warehouse.replace_table(source_table(STAGING_TABLES[source.kind], source.name), good)
    warehouse.replace_table(source_table(REJECTS_TABLE, source.name), rejects,
                            schema=REJECTS_SCHEMA)
    return log_row(run_id, source.name, sha, LOADED, result.counts)


def refresh_views(cfg, warehouse):
    """Point each view at the per-source tables of the sources in config.

    Sources that never loaded have no table and are left out; tables of
    sources removed from config stay in the dataset but drop out of the views.
    """
    existing = warehouse.list_tables()

    def tables(base, sources):
        names = [source_table(base, s.name) for s in sources]
        return [t for t in names if t in existing]

    for kind, view in STAGING_TABLES.items():
        warehouse.replace_view(view, tables(view, cfg.sources_of(kind)))
    warehouse.replace_view(REJECTS_TABLE, tables(REJECTS_TABLE, cfg.sources))


def run(cfg, warehouse, force=False, run_id=None, echo=print):
    """Load every source; returns the load_log rows written by this run."""
    run_id = run_id or new_run_id()
    warehouse.ensure_dataset()
    history = warehouse.load_log()
    written = []
    for source in cfg.sources:
        sha = None
        try:
            sha = file_sha256(source.path)
            if not force and is_unchanged(history, source.name, sha):
                row = log_row(run_id, source.name, sha, SKIPPED)
            else:
                row = load_source(source, cfg, warehouse, run_id, sha)
        except Exception as e:  # one bad file must not stop the others
            row = log_row(run_id, source.name, sha, FAILED, error=f"{type(e).__name__}: {e}")
        warehouse.append_log(row)
        written.append(row)
        echo(_summary_line(row))
    refresh_views(cfg, warehouse)
    return written


def _summary_line(row):
    if row["status"] != LOADED:
        return f"{row['source_name']:<16} {row['status']:<8} {row['error'] or ''}"
    parts = [f"{c.removeprefix('rows_')}={row[c]:,}" for c in COUNT_COLUMNS
             if row[c] or c in ("rows_read", "rows_loaded")]
    return f"{row['source_name']:<16} {row['status']:<8} " + "  ".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load HMDA sources into BigQuery staging.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--force", action="store_true", help="reload files even if unchanged")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    bq = cfg.bigquery
    warehouse = BigQueryWarehouse(bq["project"], bq["dataset"], bq["location"])
    run_id = new_run_id()
    print(f"run {run_id} -> {bq['project']}.{bq['dataset']}")
    rows = run(cfg, warehouse, force=args.force, run_id=run_id)
    failed = [r["source_name"] for r in rows if r["status"] == FAILED]
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

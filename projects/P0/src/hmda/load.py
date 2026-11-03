"""BigQuery writes, the load log and the skip check.

Each source file gets its own table (stg_lar__lar_oh_2024, rejects__lar_oh_2024,
...), loaded with WRITE_TRUNCATE, so a changed file replaces its table and a
rerun never duplicates data. Views named stg_lar, stg_filers, stg_counties and
rejects stack the per-source tables, so downstream SQL sees one table each.

This needs no DML (DELETE/UPDATE), which the BigQuery sandbox does not allow.
"""
import hashlib
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

from hmda.clean import REJECT_REASONS

STAGING_TABLES = {"lar": "stg_lar", "filers": "stg_filers", "counties": "stg_counties"}
REJECTS_TABLE = "rejects"
LOG_TABLE = "load_log"

LOADED, SKIPPED, FAILED = "loaded", "skipped", "failed"

REASON_COLUMNS = [f"rows_{r}" for r in REJECT_REASONS]
COUNT_COLUMNS = ["rows_read", "rows_filtered", "rows_rejected", *REASON_COLUMNS, "rows_loaded"]

LOG_SCHEMA = [
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("file_sha256", "STRING"),
    *[bigquery.SchemaField(c, "INT64") for c in COUNT_COLUMNS],
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("error", "STRING"),
]
REJECTS_SCHEMA = [
    bigquery.SchemaField("run_id", "STRING"),
    bigquery.SchemaField("source_name", "STRING"),
    bigquery.SchemaField("reject_reason", "STRING"),
    bigquery.SchemaField("raw_record", "STRING"),
]


# ---- naming, run id, hashing, skip check (pure, tested without BigQuery) -----

def source_table(base, source_name):
    """Physical table holding one source's rows, e.g. stg_lar__lar_oh_2024."""
    return f"{base}__{source_name}"


def new_run_id(now=None):
    """UTC timestamp like 2026-11-04T14:02:11Z; sorts in run order as text."""
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path, block_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(block_size):
            h.update(chunk)
    return h.hexdigest()


def is_unchanged(log_rows, source_name, sha):
    """True when the latest successful load of this source used this exact file.

    Only the most recent `loaded` row counts. If a file changes and is later
    put back, staging holds the changed version's rows, so the original must
    be loaded again even though its hash appears earlier in the log.
    """
    loaded = [r for r in log_rows if r["source_name"] == source_name and r["status"] == LOADED]
    if not loaded:
        return False
    return max(loaded, key=lambda r: r["run_id"])["file_sha256"] == sha


def log_row(run_id, source_name, sha, status, counts=None, error=None):
    counts = counts or {}
    return {"run_id": run_id, "source_name": source_name, "file_sha256": sha,
            **{c: counts.get(c) for c in COUNT_COLUMNS},
            "status": status, "error": error}


def schema_for(df):
    """BigQuery schema from pandas dtypes; anything that isn't a number is STRING."""
    def bq_type(dtype):
        if pd.api.types.is_bool_dtype(dtype):
            return "BOOL"
        if pd.api.types.is_integer_dtype(dtype):
            return "INT64"
        if pd.api.types.is_float_dtype(dtype):
            return "FLOAT64"
        return "STRING"
    return [bigquery.SchemaField(col, bq_type(dtype)) for col, dtype in df.dtypes.items()]


# ---- BigQuery ------------------------------------------------------------------

class BigQueryWarehouse:
    def __init__(self, project, dataset, location):
        self.client = bigquery.Client(project=project, location=location)
        self.dataset = f"{project}.{dataset}"
        self.location = location

    def _table(self, name):
        return f"{self.dataset}.{name}"

    def ensure_dataset(self):
        ds = bigquery.Dataset(self.dataset)
        ds.location = self.location
        self.client.create_dataset(ds, exists_ok=True)
        table = bigquery.Table(self._table(LOG_TABLE), schema=LOG_SCHEMA)
        self.client.create_table(table, exists_ok=True)

    def load_log(self):
        rows = self.client.query(
            f"SELECT run_id, source_name, file_sha256, status FROM `{self._table(LOG_TABLE)}`"
        ).result()
        return [dict(r) for r in rows]

    def list_tables(self):
        return {t.table_id for t in self.client.list_tables(self.dataset)}

    def replace_table(self, table, df, schema=None):
        """Overwrite `table` with `df`; an empty frame drops the table instead."""
        if df.empty:
            self.client.delete_table(self._table(table), not_found_ok=True)
            return
        job_config = bigquery.LoadJobConfig(
            schema=schema or schema_for(df),
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        self.client.load_table_from_dataframe(df, self._table(table), job_config=job_config).result()

    def replace_view(self, view, tables):
        """Point `view` at the UNION ALL of `tables`; no tables drops the view."""
        if not tables:
            self.client.delete_table(self._table(view), not_found_ok=True)
            return
        union = "\nUNION ALL\n".join(f"SELECT * FROM `{self._table(t)}`" for t in tables)
        self.client.query(f"CREATE OR REPLACE VIEW `{self._table(view)}` AS\n{union}").result()

    def append_log(self, row):
        job_config = bigquery.LoadJobConfig(
            schema=LOG_SCHEMA, write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
        self.client.load_table_from_json([row], self._table(LOG_TABLE), job_config=job_config).result()

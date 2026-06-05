"""Load a pre-built Parquet release bundle into a fresh ClickHouse warehouse.

The companion to ``etl.export_warehouse``. Given a ``release/parquet/`` folder
(downloaded from a GitHub Release or Zenodo record), this stands up the full
schema, loads the dimensions and facts, reloads dictionaries, and refreshes the
denormalized overview — giving you the exact warehouse without re-running the
ETL or downloading any sources.

    make up          # start ClickHouse (+ Grafana) first
    make restore     # then load the bundle

Idempotent: fact tables are ReplacingMergeTree, so re-running restores cleanly.
"""
from __future__ import annotations
import glob
import os

import pandas as pd

from . import db
from .config import REPO, DATABASE, SQL_DDL, DDL_FILES

RELEASE_DIR = os.path.join(REPO, "release")
PARQUET_DIR = os.path.join(RELEASE_DIR, "parquet")


def _init_schema():
    """Create database, tables, materialized views and dictionaries (DDL only)."""
    client = db.get_client(database=None)
    print("Applying schema ...")
    for f in DDL_FILES:
        db.run_sql_file(client, os.path.join(SQL_DDL, f))
    print("  schema ready")


def _load(client, path):
    table = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_parquet(path)
    client.insert_df(f"{DATABASE}.{table}", df)
    print(f"  {table:28} {len(df):>10,} rows")
    return len(df)


def restore():
    if not os.path.isdir(PARQUET_DIR):
        raise SystemExit(
            f"No bundle found at {PARQUET_DIR}.\n"
            "Download the release bundle and unzip it so the Parquet files land in "
            "release/parquet/, then re-run `make restore`.")

    files = sorted(glob.glob(os.path.join(PARQUET_DIR, "*.parquet")))
    if not files:
        raise SystemExit(f"No .parquet files in {PARQUET_DIR}.")

    dim_files = [f for f in files if os.path.basename(f).startswith("dim_")]
    fact_files = [f for f in files if os.path.basename(f).startswith("fact_")]

    _init_schema()
    client = db.get_client(DATABASE)

    print("Loading dimensions ...")
    total = sum(_load(client, f) for f in dim_files)

    # Dictionaries are populated from the dimension tables — refresh now that they exist.
    try:
        client.command("SYSTEM RELOAD DICTIONARIES")
    except Exception as e:  # non-fatal: dictionaries are an optimization, not required
        print(f"  (dictionary reload skipped: {str(e).splitlines()[0][:80]})")

    print("Loading facts ...")
    total += sum(_load(client, f) for f in fact_files)

    # Incremental materialized views populate automatically as facts are inserted.
    # The one refreshable view rebuilds on a schedule; trigger it now for an instant
    # populated overview.
    try:
        client.command(f"SYSTEM REFRESH VIEW {DATABASE}.mv_country_year_overview")
    except Exception:
        pass

    sources = client.query(
        f"SELECT count(DISTINCT source_id) FROM {DATABASE}.fact_emissions_co2"
    ).result_rows
    print(f"\nRestore complete: {total:,} rows loaded across "
          f"{len(dim_files)} dimensions + {len(fact_files)} fact tables.")
    print("Run `make dq` to confirm the data-quality scorecard, then open Grafana.")


if __name__ == "__main__":
    restore()

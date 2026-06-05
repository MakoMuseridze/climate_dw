"""ClickHouse connection + insert/lineage helpers (clickhouse-connect)."""
from __future__ import annotations
import datetime as _dt
import re
import pandas as pd
import clickhouse_connect

from .config import CLICKHOUSE, DATABASE


def get_client(database: str | None = None):
    """Return a clickhouse-connect client. Pass database=None for server-level
    DDL (e.g. CREATE DATABASE); otherwise defaults to the warehouse DB."""
    kwargs = dict(CLICKHOUSE)
    if database is not None:
        kwargs["database"] = database
    return clickhouse_connect.get_client(**kwargs)


def split_statements(sql: str) -> list[str]:
    """Strip -- line comments and split a script into individual statements."""
    sql = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in sql.split(";") if s.strip()]


def run_sql_file(client, path: str) -> int:
    n = 0
    with open(path, encoding="utf-8") as fh:
        for stmt in split_statements(fh.read()):
            client.command(stmt)
            n += 1
    return n


def insert_dataframe(client, table: str, df: pd.DataFrame, *, source_id: int,
                     source_name: str, url: str = "", file_name: str = "",
                     access_date: _dt.date | None = None, notes: str = "") -> int:
    """Insert a DataFrame into climate.<table> and record a lineage row.

    The DataFrame's columns must match the target table's column names
    (meta columns with DEFAULTs may be omitted)."""
    started = _dt.datetime.now().replace(microsecond=0)
    rows = int(len(df))
    if rows:
        client.insert_df(f"{DATABASE}.{table}", df)
    finished = _dt.datetime.now().replace(microsecond=0)

    client.insert(
        f"{DATABASE}.meta_load_lineage",
        [[source_id, source_name, table, file_name, url, rows,
          started, finished, "SUCCESS", "", access_date or _dt.date.today(), notes]],
        column_names=["source_id", "source_name", "target_table", "file_name",
                      "source_url", "rows_loaded", "load_started", "load_finished",
                      "status", "checksum", "access_date", "notes"],
    )
    return rows


def log_failed_load(client, table: str, *, source_id: int, source_name: str,
                    url: str = "", notes: str = "") -> None:
    now = _dt.datetime.now().replace(microsecond=0)
    client.insert(
        f"{DATABASE}.meta_load_lineage",
        [[source_id, source_name, table, "", url, 0, now, now, "FAILED", "",
          _dt.date.today(), notes[:500]]],
        column_names=["source_id", "source_name", "target_table", "file_name",
                      "source_url", "rows_loaded", "load_started", "load_finished",
                      "status", "checksum", "access_date", "notes"],
    )

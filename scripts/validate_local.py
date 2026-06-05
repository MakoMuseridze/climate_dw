"""Offline end-to-end self-test using embedded ClickHouse (chdb) — no server,
no network. Stands up the full schema, loads a representative fixture, runs the
analytical query library with timings, and runs the data-quality suite.

This validates the SQL/schema/MV/DQ logic; production loads real data through
the same objects. Run:  python scripts/validate_local.py   (or `make validate`)
"""
from __future__ import annotations
import os
import re
import sys
import time
import tempfile

import pandas as pd
import pyarrow.parquet as pq

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from chdb import session as chs            # noqa: E402
from etl.synthetic import generate as G    # fixture only  # noqa: E402
from etl import dq                          # noqa: E402

DDL = ["00_database.sql", "01_dimensions.sql", "02_facts.sql",
       "03_materialized_views.sql", "05_lineage_audit.sql"]
DATE_COLS = {"date", "valid_from", "valid_to"}


def _statements(path):
    sql = re.sub(r"--[^\n]*", "", open(path, encoding="utf-8").read())
    return [s.strip() for s in sql.split(";") if s.strip()]


def main():
    work = tempfile.mkdtemp(prefix="climate_ch_")
    sess = chs.Session(os.path.join(work, "db"))
    pdir = os.path.join(work, "parq"); os.makedirs(pdir)

    # 1) schema
    for f in DDL:
        for st in _statements(os.path.join(REPO, "sql", "ddl", f)):
            sess.query(st)
    print("schema: created")

    # 2) fixture data
    print("generating fixture ...")
    countries = G.build_countries()
    tables = {"dim_country": countries, "dim_date": G.build_dim_date(),
              "dim_indicator": G.build_indicators(), "dim_disaster_type": G.build_disaster_types(),
              "dim_sector": G.build_sectors(), "dim_source": G.build_sources(),
              **G.build_facts(countries)}

    def load(table, df):
        df = df.copy()
        for c in df.columns:
            if c in DATE_COLS:
                df[c] = pd.to_datetime(df[c]).dt.date
        p = os.path.join(pdir, f"{table}.parquet")
        df.to_parquet(p, index=False)
        cols = ",".join(f"`{c}`" for c in pq.ParquetFile(p).schema.names)
        sess.query(f"INSERT INTO climate.{table} ({cols}) SELECT {cols} "
                   f"FROM file('{p}', Parquet)")
        return len(df)

    fact_rows = 0
    for name, df in tables.items():
        n = load(name, df)
        if name.startswith("fact_"):
            fact_rows += n
    print(f"loaded: {fact_rows:,} fact rows across {sum(k.startswith('fact_') for k in tables)} fact tables")

    # 3) analytical queries + benchmark
    print("\n--- analytical query library (target < 2000 ms) ---")
    qs = _statements(os.path.join(REPO, "sql", "queries", "analytical_queries.sql"))
    slow = 0
    for i, q in enumerate(qs, 1):
        t0 = time.time()
        res = sess.query(q, "CSV")
        ms = (time.time() - t0) * 1000
        nrows = len(str(res).strip().splitlines())
        flag = "ok" if ms < 2000 else "SLOW"
        if ms >= 2000:
            slow += 1
        print(f"Q{i:<2} {ms:8.1f} ms  rows~{nrows:<5} {flag}")

    # 4) data-quality suite
    print("\n--- data-quality suite ---")
    def scalar(sql):
        out = str(sess.query(sql, "CSV")).strip().strip('"')
        return None if out == "" else float(out.splitlines()[0])
    _, rate = dq.run(scalar)

    print("\n=== SUMMARY ===")
    print(f"fact rows           : {fact_rows:,}")
    print(f"queries < 2s        : {len(qs) - slow}/{len(qs)}")
    print(f"DQ pass rate        : {rate:.1f}%")
    ok = (slow == 0 and rate >= 95 and fact_rows >= 500_000)
    print("RESULT:", "PASS" if ok else "REVIEW")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

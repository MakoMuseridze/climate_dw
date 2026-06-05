"""Export the loaded warehouse to a portable Parquet bundle for distribution.

Dumps every dimension and fact table from the running ClickHouse warehouse to
compressed Parquet under ``release/``, plus a ``MANIFEST.json`` and an
``ATTRIBUTION.md``. The bundle can be attached to a GitHub Release or Zenodo
record and reloaded with ``python -m etl.restore_warehouse`` (``make restore``)
on any machine — no source downloads, registrations, or re-running the ETL.

    make export                  # full bundle (all loaded sources)
    make export ARGS=--public    # redistribution-safe subset (see below)
    # Windows / no make:  python -m etl.export_warehouse [--public]

Licensing: most sources are CC-BY or public domain (fine to redistribute with
attribution). ``--public`` drops the two with restrictive terms — ND-GAIN
(CC-BY-NC-SA) and EM-DAT (free, registration; redistribution restricted) — so
the resulting bundle is safe to publish openly. Always confirm each source's
current licence before releasing a bundle; see ATTRIBUTION.md in the output.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os

import pyarrow  # noqa: F401  -- ensures the Parquet engine is available

from . import db
from .config import REPO, DATABASE
from .sources import SOURCES

RELEASE_DIR = os.path.join(REPO, "release")
PARQUET_DIR = os.path.join(RELEASE_DIR, "parquet")
COMPRESSION = "zstd"

# Sources whose licence restricts open redistribution; excluded by --public.
RESTRICTED_SOURCE_IDS = {4, 5}   # 4 = ND-GAIN (CC-BY-NC-SA), 5 = EM-DAT (registration)
META_COLUMNS = {"_inserted_at", "_version"}
# MergeTree variants that support SELECT ... FINAL (collapse not-yet-merged rows).
# Plain MergeTree does NOT, so FINAL is applied only where the engine allows it.
FINAL_ENGINES = ("Replacing", "Aggregating", "Summing", "Collapsing")


def _scalar(client, sql):
    return client.query(sql).result_rows[0][0]


def _table_engines(client):
    rows = client.query(
        f"SELECT name, engine FROM system.tables WHERE database='{DATABASE}' "
        f"AND (startsWith(name, 'dim_') OR startsWith(name, 'fact_')) ORDER BY name"
    ).result_rows
    return [(r[0], r[1]) for r in rows]


def _supports_final(engine: str) -> bool:
    return any(k in engine for k in FINAL_ENGINES)


def _insertable_columns(client, table):
    """Business columns only: skip MATERIALIZED/ALIAS and load-bookkeeping columns."""
    rows = client.query(
        f"SELECT name FROM system.columns WHERE database='{DATABASE}' AND table='{table}' "
        f"AND default_kind NOT IN ('MATERIALIZED', 'ALIAS') ORDER BY position"
    ).result_rows
    return [r[0] for r in rows if r[0] not in META_COLUMNS]


def export(public: bool = False):
    client = db.get_client(DATABASE)
    os.makedirs(PARQUET_DIR, exist_ok=True)
    tables = _table_engines(client)
    dims = [n for n, _ in tables if n.startswith("dim_")]
    facts = [n for n, _ in tables if n.startswith("fact_")]
    engine_of = {n: e for n, e in tables}

    manifest = {
        "warehouse": "Global Climate Data Warehouse",
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mode": "public" if public else "full",
        "clickhouse_version": _scalar(client, "SELECT version()"),
        "tables": {},
    }

    print(f"Exporting {'PUBLIC subset' if public else 'FULL warehouse'} -> {PARQUET_DIR}")
    for t in dims + facts:
        cols = _insertable_columns(client, t)
        col_sql = ", ".join(f"`{c}`" for c in cols)
        final = " FINAL" if _supports_final(engine_of.get(t, "")) else ""
        where = ""
        if public and t in facts and "source_id" in cols:
            ids = ", ".join(str(i) for i in sorted(RESTRICTED_SOURCE_IDS))
            where = f" WHERE source_id NOT IN ({ids})"
        df = client.query_df(f"SELECT {col_sql} FROM {DATABASE}.`{t}`{final}{where}")
        if public and t in facts and len(df) == 0:
            print(f"  skip {t:28} (no redistributable rows)")
            continue
        path = os.path.join(PARQUET_DIR, f"{t}.parquet")
        df.to_parquet(path, index=False, compression=COMPRESSION)
        size_mb = os.path.getsize(path) / 1e6
        manifest["tables"][t] = {"rows": int(len(df)), "bytes": os.path.getsize(path)}
        print(f"  {t:28} {len(df):>10,} rows  ->  {size_mb:6.1f} MB")

    manifest["total_fact_rows"] = sum(
        v["rows"] for k, v in manifest["tables"].items() if k.startswith("fact_"))

    included = [s for s in SOURCES if s["source_id"] != 99
                and not (public and s["source_id"] in RESTRICTED_SOURCE_IDS)]
    manifest["sources"] = [
        {"name": s["source_name"], "license": s["license"], "url": s["url"]} for s in included]

    with open(os.path.join(RELEASE_DIR, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    _write_attribution(included, public)

    total_bytes = sum(v["bytes"] for v in manifest["tables"].values())
    print(f"\nBundle ready: {RELEASE_DIR}")
    print(f"  {manifest['total_fact_rows']:,} fact rows · "
          f"{len(manifest['tables'])} tables · {total_bytes / 1e6:.1f} MB total")
    print("  Next: zip the release/ folder and attach it to a GitHub Release or Zenodo record.")
    print("        Recipients reload it with `make restore` (or python -m etl.restore_warehouse).")


def _write_attribution(sources, public):
    lines = [
        "# Data sources & attribution",
        "",
        "This bundle contains data harmonized from the sources below. Each dataset "
        "remains under its original licence — cite and comply with each accordingly.",
        "",
    ]
    if not public:
        lines += [
            "> **Note:** this is a FULL bundle and includes ND-GAIN (CC-BY-NC-SA) and "
            "EM-DAT (free, registration — redistribution restricted). Confirm their "
            "terms before publishing this bundle openly, or regenerate a redistribution-"
            "safe subset with `make export ARGS=--public`.",
            "",
        ]
    lines += ["| Source | Licence | URL |", "|--------|---------|-----|"]
    lines += [f"| {s['source_name']} | {s['license']} | {s['url']} |" for s in sources]
    with open(os.path.join(RELEASE_DIR, "ATTRIBUTION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Export the warehouse to a Parquet release bundle")
    ap.add_argument("--public", action="store_true",
                    help="exclude redistribution-restricted sources (ND-GAIN, EM-DAT)")
    args = ap.parse_args()
    export(public=args.public)


if __name__ == "__main__":
    main()

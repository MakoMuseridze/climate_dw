"""ETL orchestrator.

Examples
--------
  python -m etl.run_etl --init-schema           # create DB, tables, MVs, dicts
  python -m etl.run_etl --seed                  # load dimensions / reference data
  python -m etl.run_etl --group quick           # fully-automatic public sources
  python -m etl.run_etl --sources owid_co2 wdi  # specific sources
  python -m etl.run_etl --all                   # everything available
  python -m etl.run_etl --group quick --dry-run # extract + preview, no load
  python -m etl.run_etl --bootstrap             # init-schema + seed + group quick
"""
from __future__ import annotations
import argparse
import os
import sys
import time
import traceback

from .config import DATABASE, SQL_DDL, DDL_FILES
from . import db
from .countries import CountryResolver

from .real.owid_co2 import OwidCo2
from .real.owid_energy import OwidEnergy
from .real.worldbank_wdi import WorldBankWDI
from .real.noaa_co2 import NoaaCo2
from .real.gistemp import Gistemp
from .real.ndgain import NdGain
from .real.global_carbon_budget import GlobalCarbonBudget
from .real.csiro_sealevel import CsiroSeaLevel
from .real.emdat import EmDat
from .real.edgar import Edgar
from .real.faostat import Faostat
from .real.climate_trace import ClimateTrace
from .real.forest_watch import ForestWatch
from .real.era5 import Era5
from .real.gridded import HadCrut5, NoaaGlobalTemp, Gpcc

REGISTRY = {
    "owid_co2": OwidCo2, "owid_energy": OwidEnergy, "wdi": WorldBankWDI,
    "noaa_co2": NoaaCo2, "gistemp": Gistemp, "ndgain": NdGain,
    "gcb": GlobalCarbonBudget, "csiro_sealevel": CsiroSeaLevel, "emdat": EmDat,
    "edgar": Edgar, "faostat": Faostat, "climate_trace": ClimateTrace,
    "forest_watch": ForestWatch, "era5": Era5, "hadcrut5": HadCrut5,
    "noaaglobaltemp": NoaaGlobalTemp, "gpcc": Gpcc,
}
GROUPS = {
    "quick": ["owid_co2", "owid_energy", "wdi", "noaa_co2", "gistemp"],
    "file": ["ndgain", "gcb", "csiro_sealevel", "emdat", "edgar", "faostat",
             "climate_trace", "forest_watch"],
    "gridded": ["hadcrut5", "noaaglobaltemp", "gpcc", "era5"],
}
GROUPS["all"] = GROUPS["quick"] + GROUPS["file"] + GROUPS["gridded"]


def init_schema():
    client = db.get_client(database=None)
    print("Applying DDL ...")
    for f in DDL_FILES:
        try:
            n = db.run_sql_file(client, os.path.join(SQL_DDL, f))
            print(f"  {f:32} {n} statements")
        except Exception as e:
            print(f"  {f:32} ERROR: {str(e).splitlines()[0][:120]}")
    print("Schema ready.")


def seed():
    from .seed_dimensions import seed as _seed
    print("Seeding dimensions ...")
    _seed(db.get_client(database=DATABASE))


def run_sources(names, dry_run=False):
    client = db.get_client(database=DATABASE)
    resolver = CountryResolver(client)
    total = 0
    print(f"\n{'source':16} {'rows':>10}  status")
    print("-" * 60)
    for name in names:
        cls = REGISTRY[name]
        ex = cls(client=client, resolver=resolver)
        t0 = time.time()
        try:
            rows, note = ex.run(dry_run=dry_run)
            n = len(rows) if dry_run else rows
            total += (0 if dry_run else n)
            print(f"{name:16} {n:>10,}  ok ({time.time()-t0:.1f}s) {note}")
            if dry_run:
                with_cols = list(rows.columns)
                print(f"                 preview cols={with_cols}")
                print(rows.head(3).to_string(max_colwidth=24))
        except Exception as e:
            if not dry_run:
                try:
                    db.log_failed_load(client, cls.target_table, source_id=cls.source_id,
                                       source_name=cls.source_name, url="", notes=str(e)[:300])
                except Exception:
                    pass
            print(f"{name:16} {'-':>10}  FAIL: {str(e).splitlines()[0][:90]}")
            if os.getenv("ETL_DEBUG"):
                traceback.print_exc()
    print("-" * 60)
    print(f"{'TOTAL loaded':16} {total:>10,} rows")


def resolve_names(args) -> list:
    names = []
    if args.group:
        names += GROUPS.get(args.group, [])
    if args.all:
        names = GROUPS["all"]
    if args.sources:
        names += args.sources
    # de-dup preserve order
    seen, out = set(), []
    for n in names:
        if n in REGISTRY and n not in seen:
            seen.add(n); out.append(n)
        elif n not in REGISTRY:
            print(f"unknown source: {n} (known: {list(REGISTRY)})")
    return out


def main():
    ap = argparse.ArgumentParser(description="Climate DW ETL orchestrator")
    ap.add_argument("--init-schema", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--bootstrap", action="store_true",
                    help="init-schema + seed + load group 'quick'")
    ap.add_argument("--group", choices=list(GROUPS))
    ap.add_argument("--sources", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true", help="list known sources/groups")
    args = ap.parse_args()

    if args.list:
        print("sources:", list(REGISTRY))
        print("groups :", {k: v for k, v in GROUPS.items()})
        return
    if args.bootstrap:
        init_schema(); seed(); run_sources(GROUPS["quick"], dry_run=args.dry_run); return
    if args.init_schema:
        init_schema()
    if args.seed:
        seed()
    names = resolve_names(args)
    if names:
        run_sources(names, dry_run=args.dry_run)
    elif not (args.init_schema or args.seed):
        ap.print_help()


if __name__ == "__main__":
    sys.exit(main())

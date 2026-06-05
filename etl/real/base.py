"""Base class for source extractors.

Subclass contract
-----------------
    class MyExtractor(Extractor):
        source_id    = 1
        source_name  = "OWID CO2 Data"
        target_table = "fact_emissions_co2"
        def extract(self) -> pd.DataFrame:
            path = self.fetch(self.source_url, "owid-co2-data.csv")
            df = pd.read_csv(path)
            ...
            return df   # columns == target table columns (incl country_id, source_id)

`run()` handles download caching, light type coercion, loading, and lineage.
Downloads run on the user's machine (network + any registered credentials).
"""
from __future__ import annotations
import os
import glob
import pandas as pd

from ..config import DATA_RAW
from ..sources import get as get_source
from .. import db


class Extractor:
    source_id: int = 0
    source_name: str = ""
    target_table: str = ""
    #: columns that must be integers in the target table
    int_cols: tuple = ("country_id", "year", "indicator_id", "sector_id",
                        "disaster_type_id", "events", "total_deaths", "total_affected",
                        "source_id")

    def __init__(self, client=None, resolver=None, raw_dir: str = DATA_RAW):
        self.client = client
        self.resolver = resolver
        self.raw_dir = raw_dir

    @property
    def source_url(self) -> str:
        return get_source(self.source_id)["url"]

    # ---------------------------------------------------------------- download
    def fetch(self, url: str, filename: str, timeout: int = 180) -> str:
        """Download `url` to data/raw/<filename> (cached; skip if present)."""
        path = os.path.join(self.raw_dir, filename)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        import requests
        with requests.get(url, stream=True, timeout=timeout,
                          headers={"User-Agent": "climate-dw-etl/1.0"}) as r:
            r.raise_for_status()
            tmp = path + ".part"
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
            os.replace(tmp, path)
        return path

    def find_local(self, *patterns: str) -> str | None:
        """Return the first file in data/raw matching any glob pattern."""
        for pat in patterns:
            hits = sorted(glob.glob(os.path.join(self.raw_dir, pat))
                          + glob.glob(os.path.join(self.raw_dir, "**", pat), recursive=True))
            if hits:
                return hits[0]
        return None

    def local_or_fetch(self, patterns: list[str], url: str | None,
                       filename: str | None, hint: str = "") -> str:
        """Use a user-placed file (matching patterns) if present, else download
        from `url`. Raise a clear instruction if neither is possible."""
        local = self.find_local(*patterns)
        if local:
            return local
        if url:
            return self.fetch(url, filename or os.path.basename(url))
        raise FileNotFoundError(
            f"[{self.source_name}] needs a manual download. {hint}\n"
            f"Place the file in data/raw/ matching one of: {patterns}")

    # ---------------------------------------------------------------- override
    def extract(self) -> pd.DataFrame:
        raise NotImplementedError

    # ---------------------------------------------------------------- finalize
    def _finalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if "country_id" in df.columns:
            df = df[df["country_id"].notna()].copy()
        for c in self.int_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "country_id" in df.columns:
            df = df[df["country_id"].notna()].copy()
            df["country_id"] = df["country_id"].astype("int64")
        for c in self.int_cols:
            if c in df.columns:
                df[c] = df[c].fillna(0).astype("int64")
        if "source_id" not in df.columns:
            df["source_id"] = self.source_id
        # convert date columns to python date
        import datetime as _d
        for c in ("date",):
            if c in df.columns:
                df[c] = pd.to_datetime(df[c]).dt.date
                df = df[df[c] >= _d.date(1900, 1, 1)]
        return df.reset_index(drop=True)

    # ---------------------------------------------------------------- run
    def run(self, dry_run: bool = False):
        df = self.extract()
        df = self._finalize(df)
        note = ""
        if self.resolver is not None:
            note = self.resolver.report()
        if dry_run:
            return df, note
        rows = db.insert_dataframe(
            self.client, self.target_table, df,
            source_id=self.source_id, source_name=self.source_name,
            url=self.source_url, notes=note)
        return rows, note
